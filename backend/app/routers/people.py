from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app import repo
from app.auth import current_user
from app.config import settings
from app.llm import LLMError
from app.search import SearchError
from app.services import competitors, people

router = APIRouter(tags=["people"])


def _lead_or_404(user, lead_id: str) -> dict:
    lead = repo.get_lead(user.id, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


def _campaign_or_404(user, campaign_id: str) -> dict:
    c = repo.get_campaign(user.id, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c


@router.post("/leads/{lead_id}/people")
def find_one(lead_id: str, user=Depends(current_user)):
    """Find the people at one lead's company right now."""
    lead = _lead_or_404(user, lead_id)
    campaign = _campaign_or_404(user, lead["campaign_id"])
    try:
        contacts = people.find_people(user.id, campaign, lead)
    except people.PeopleError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"contacts": contacts, "lead": repo.get_lead(user.id, lead_id)}


@router.post("/campaigns/{campaign_id}/people")
def find_for_campaign(campaign_id: str, background: BackgroundTasks, user=Depends(current_user)):
    """Queue a people search for researched, good-fit leads that have none yet."""
    campaign = _campaign_or_404(user, campaign_id)
    done = repo.lead_ids_with_contacts(user.id, campaign_id)
    ids = [l["id"] for l in repo.list_leads(user.id, campaign_id, ["researched"])
           if (l.get("fit_score") or 0) >= settings.min_fit_to_draft and l.get("domain") and l["id"] not in done]
    if ids:
        background.add_task(people.find_many, user.id, campaign, ids)
    return {"queued": len(ids)}


@router.post("/leads/{lead_id}/contacts/{contact_id}/use")
def use_contact(lead_id: str, contact_id: str, user=Depends(current_user)):
    """Write this lead's email to a different person."""
    lead = _lead_or_404(user, lead_id)
    contact = repo.get_contact(user.id, contact_id)
    if not contact or contact["lead_id"] != lead_id:
        raise HTTPException(404, "Contact not found")
    try:
        updated = people.use_contact(user.id, lead, contact)
    except people.ContactBlocked as exc:
        raise HTTPException(409, str(exc)) from exc
    latest = repo.get_latest_email(user.id, lead_id)
    return {"lead": updated, "draft_outdated": bool(latest and latest["status"] in ("draft", "failed", "rejected"))}


@router.post("/campaigns/{campaign_id}/competitors")
def find_competitors(campaign_id: str, user=Depends(current_user)):
    campaign = _campaign_or_404(user, campaign_id)
    if not (campaign.get("product_pitch") or "").strip():
        raise HTTPException(409, "Add what you sell to this campaign first. Competitors are found from it.")
    try:
        return {"competitors": competitors.refresh(user.id, campaign)}
    except (LLMError, SearchError) as exc:
        raise HTTPException(502, str(exc)) from exc
