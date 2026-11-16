import csv
import io
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from app import repo
from app.auth import current_user
from app.llm import LLMError
from app.net import clean_domain
from app.schemas import CampaignCreate, CampaignEdit, CsvImport
from app.search import SearchError
from app.services import discovery, icp as icp_service, research
from app.services.seed import SEED_LEADS

router = APIRouter(tags=["campaigns"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CSV_ALIASES = {
    "company_name": ["company_name", "company", "organization", "organisation"],
    "domain": ["domain", "website", "url"],
    "contact_name": ["contact_name", "contact", "full_name"],
    "contact_role": ["contact_role", "role", "title", "job_title"],
    "contact_email": ["contact_email", "email"],
}


def _campaign_or_404(user, campaign_id: str) -> dict:
    c = repo.get_campaign(user.id, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c


def _parse_icp_into(user, campaign: dict) -> tuple[dict, str | None]:
    """Run the ICP step. On provider failure keep the campaign and return a warning to show the user."""
    try:
        icp = icp_service.parse_icp(campaign["product_pitch"], campaign["icp_description"])
    except LLMError as exc:
        return campaign, str(exc)
    return repo.update_campaign(user.id, campaign["id"], {"icp": icp.model_dump()}) or campaign, None


@router.post("/campaigns")
def create_campaign(body: CampaignCreate, user=Depends(current_user)):
    campaign = repo.create_campaign(user.id, {"name": body.name.strip(), "product_pitch": body.product_pitch.strip(), "icp_description": body.icp_description.strip(), "status": "draft"})
    campaign, warning = _parse_icp_into(user, campaign)
    return {"campaign": campaign, "warning": warning}


@router.post("/campaigns/{campaign_id}/icp")
def regenerate_icp(campaign_id: str, body: CampaignEdit | None = None, user=Depends(current_user)):
    campaign = _campaign_or_404(user, campaign_id)
    edits = {k: v.strip() for k, v in (body.model_dump(exclude_none=True) if body else {}).items()}
    if edits:
        campaign = repo.update_campaign(user.id, campaign_id, edits) or campaign
    campaign, warning = _parse_icp_into(user, campaign)
    if warning:
        raise HTTPException(502, warning)
    return {"campaign": campaign}


@router.post("/campaigns/{campaign_id}/discover")
def discover_leads(campaign_id: str, user=Depends(current_user)):
    campaign = _campaign_or_404(user, campaign_id)
    if not campaign.get("icp"):
        raise HTTPException(409, "This campaign has no ideal customer profile yet. Generate it first.")
    try:
        return discovery.discover(user.id, campaign)
    except (LLMError, SearchError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/campaigns/{campaign_id}/seed")
def seed_leads(campaign_id: str, user=Depends(current_user)):
    """Fictional demo leads so the demo never depends on live search."""
    _campaign_or_404(user, campaign_id)
    rows = [{**r, "source": "seed"} for r in SEED_LEADS]
    return {"added": repo.insert_leads(user.id, campaign_id, rows)}


@router.post("/campaigns/{campaign_id}/leads/import")
def import_leads(campaign_id: str, body: CsvImport, user=Depends(current_user)):
    _campaign_or_404(user, campaign_id)
    reader = csv.DictReader(io.StringIO(body.csv))
    if not reader.fieldnames:
        raise HTTPException(422, "The CSV has no header row.")
    headers = {h: (h or "").strip().lower().replace(" ", "_") for h in reader.fieldnames}
    rows, skipped = [], 0
    for i, raw in enumerate(reader):
        if i >= 200:
            skipped += 1
            continue
        norm = {headers[k]: (v or "").strip() for k, v in raw.items() if k in headers}
        pick = {field: next((norm[a] for a in aliases if norm.get(a)), "") for field, aliases in CSV_ALIASES.items()}
        domain = clean_domain(pick["domain"])
        if not pick["company_name"] or (pick["domain"] and not domain):
            skipped += 1
            continue
        email = pick["contact_email"] if EMAIL_RE.match(pick["contact_email"]) else None
        rows.append({"company_name": pick["company_name"][:200], "domain": domain, "contact_name": pick["contact_name"] or None,
                     "contact_role": pick["contact_role"] or None, "contact_email": email, "source": "csv"})
    added = repo.insert_leads(user.id, campaign_id, rows)
    return {"added": added, "skipped": skipped + (len(rows) - added)}


@router.post("/campaigns/{campaign_id}/research")
def research_campaign(campaign_id: str, background: BackgroundTasks, force: bool = Query(False), user=Depends(current_user)):
    """Queue research for leads that are new or failed. force=true also re-queues leads stuck in 'researching'."""
    campaign = _campaign_or_404(user, campaign_id)
    if not campaign.get("icp"):
        raise HTTPException(409, "This campaign has no ideal customer profile yet. Generate it first.")
    statuses = ["new", "failed"] + (["researching"] if force else [])
    ids = [l["id"] for l in repo.list_leads(user.id, campaign_id, statuses)]
    if ids:
        background.add_task(research.research_many, user.id, campaign, ids, statuses)
    return {"queued": len(ids)}


@router.post("/leads/{lead_id}/research")
def research_one(lead_id: str, user=Depends(current_user)):
    """Research (or re-research) a single lead right now."""
    lead = repo.get_lead(user.id, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    campaign = _campaign_or_404(user, lead["campaign_id"])
    if not campaign.get("icp"):
        raise HTTPException(409, "This campaign has no ideal customer profile yet. Generate it first.")
    return {"lead": research.research_lead(user.id, campaign, lead)}
