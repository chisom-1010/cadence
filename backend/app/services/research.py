"""Research one lead: read its website, then ask the LLM for a short summary, a fit score and a hook.
The model only sees the website text, and the prompt forbids claims that are not in it."""
import time

from app import repo
from app.config import settings
from app.llm import LLMError, LLMRateLimited, complete_json
from app.net import fetch_site_text
from app.schemas import ICP, ResearchOut

SYSTEM = """You research a company for a sales team using ONLY the website text provided.
Rules:
- summary: at most 60 words on what the company does and who it serves. Do not state anything the text does not say.
- fit_score: 0 to 100, how well the company matches the ideal customer profile. Below 40 means a poor match.
- fit_reason: one sentence explaining the score.
- personalization_hook: one specific detail from the text (a product, a recent announcement, a stated goal) that could open a cold email. Use null if the text has nothing specific.
- If the text says very little, give a low-confidence score and say so in fit_reason."""

MIN_TEXT = 200
RETRY_STATUSES = ["new", "failed"]


def research_lead(user_id: str, campaign: dict, lead: dict, *, already_claimed: bool = False) -> dict:
    """Returns the updated lead. Never raises for provider problems; it records them on the lead."""
    if not already_claimed and repo.claim_lead(user_id, lead["id"], RETRY_STATUSES + ["researching", "researched", "no_data"]) is None:
        return lead

    text = lead.get("website_text") or None
    if not text:
        text = fetch_site_text(lead["domain"], settings.website_text_chars) if lead.get("domain") else None
    if not text or len(text) < MIN_TEXT:
        return repo.update_lead(user_id, lead["id"], {"status": "no_data", "error": "Website text could not be read."}) or lead

    icp = ICP.model_validate(campaign["icp"])
    user = (
        f"Ideal customer profile: {icp.model_dump_json()}\n"
        f"What we sell: {campaign.get('product_pitch') or '(not provided)'}\n\n"
        f"Company: {lead['company_name']} ({lead.get('domain') or 'no domain'})\n"
        f"Website text:\n{text[: settings.website_text_chars]}"
    )
    model = settings.llm_model_fast or settings.llm_model or None
    try:
        out = complete_json(SYSTEM, user, ResearchOut, model=model, temperature=0.2, max_tokens=500)
    except LLMRateLimited as exc:
        return repo.update_lead(user_id, lead["id"], {"status": "failed", "error": str(exc)[:300]}) or lead
    except LLMError as exc:
        return repo.update_lead(user_id, lead["id"], {"status": "failed", "error": str(exc)[:300]}) or lead

    return repo.update_lead(user_id, lead["id"], {
        "website_text": text[: settings.website_text_chars],
        "research_summary": out.summary.strip(),
        "fit_score": out.fit_score,
        "fit_reason": out.fit_reason.strip(),
        "personalization_hook": (out.personalization_hook or "").strip() or None,
        "status": "researched",
        "error": None,
    }) or lead


def research_many(user_id: str, campaign: dict, lead_ids: list[str], claim_from: list[str] | None = None) -> None:
    """Background job: one lead at a time, with a pause to respect free-tier request limits."""
    claim_from = claim_from or RETRY_STATUSES
    for lead_id in lead_ids:
        try:
            lead = repo.get_lead(user_id, lead_id)
            if lead and repo.claim_lead(user_id, lead_id, claim_from):
                research_lead(user_id, campaign, lead, already_claimed=True)
        except Exception as exc:  # noqa: BLE001  keep the batch going; the lead keeps a visible error
            repo.update_lead(user_id, lead_id, {"status": "failed", "error": f"Unexpected error: {exc}"[:300]})
        time.sleep(settings.research_delay_seconds)
