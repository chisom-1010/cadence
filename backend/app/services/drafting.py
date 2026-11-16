"""Write one cold email per researched lead. The model only sees facts we already stored from the
lead's own website, and the prompt forbids inventing anything else."""
import time

from app import repo
from app.config import settings
from app.llm import LLMError, complete_json
from app.schemas import DraftOut, ICP

SYSTEM = """You write one short cold email from a sales rep to a prospect.
Hard rules:
- Use ONLY the facts given below. Never invent statistics, customers, results, prices, mutual contacts, or past conversations. Never claim to have used or reviewed the prospect's product.
- Mention the personalization hook naturally in the first sentence if one is given. If none is given, open with what the company does, as stated in the summary.
- Address the contact by first name if a name is given, otherwise start with "Hi there,".
- Say what we offer in one sentence, tied to a pain point only if it plausibly fits the summary.
- End with one low-pressure ask (a short reply or a 15 minute call) and a one-line way to opt out, such as "If this is not relevant, tell me and I will not follow up."
- Plain text. No bullet points, no emojis, no hype words, no signature (it is added later). 60 to 120 words.
- No placeholders in square brackets or braces. Write the final text."""


class DraftBlocked(Exception):
    """The lead cannot be drafted right now (already approved or sent)."""


def _facts(campaign: dict, lead: dict) -> str:
    icp = ICP.model_validate(campaign["icp"]) if campaign.get("icp") else None
    pains = ", ".join(icp.pain_points) if icp and icp.pain_points else "(none listed)"
    return (
        f"What we offer: {campaign.get('product_pitch') or '(not provided)'}\n"
        f"Pain points we usually solve: {pains}\n\n"
        f"Prospect company: {lead['company_name']} ({lead.get('domain') or 'no domain'})\n"
        f"Contact: {lead.get('contact_name') or '(unknown)'}, {lead.get('contact_role') or 'role unknown'}\n"
        f"What the company does (from its website): {lead.get('research_summary') or '(unknown)'}\n"
        f"Personalization hook: {lead.get('personalization_hook') or '(none)'}"
    )


def draft_lead(user_id: str, campaign: dict, lead: dict) -> dict:
    """Create or refresh the draft for a lead and return the email row. Raises LLMError on provider
    problems and DraftBlocked when the lead's email is already approved or sent."""
    existing = repo.get_latest_email(user_id, lead["id"])
    if existing and existing["status"] in ("approved", "sent"):
        raise DraftBlocked("This lead already has an approved or sent email.")

    out = complete_json(SYSTEM, _facts(campaign, lead), DraftOut, model=settings.llm_model or None, temperature=0.5, max_tokens=1500)
    fields = {"subject": out.subject, "body": f"{out.body}\n\n{settings.sender_name}", "status": "draft",
              "error": None, "approved_at": None, "sent_at": None, "sent_to": None}
    if existing:
        email = repo.transition_email(user_id, existing["id"], ["draft", "rejected", "failed"], fields)
        if email is None:
            raise DraftBlocked("This email changed while drafting. Refresh and try again.")
    else:
        email = repo.insert_email(user_id, {**fields, "lead_id": lead["id"], "campaign_id": lead["campaign_id"]})
    repo.update_lead(user_id, lead["id"], {"status": "drafted", "error": None})
    return email


def draft_many(user_id: str, campaign: dict, lead_ids: list[str]) -> None:
    """Background job: one lead at a time. A failure is saved on the lead and the batch carries on."""
    for lead_id in lead_ids:
        try:
            lead = repo.get_lead(user_id, lead_id)
            if lead and lead["status"] == "researched":
                draft_lead(user_id, campaign, lead)
        except DraftBlocked:
            pass
        except LLMError as exc:
            repo.update_lead(user_id, lead_id, {"error": f"Draft failed: {exc}"[:300]})
        except Exception as exc:  # noqa: BLE001
            repo.update_lead(user_id, lead_id, {"error": f"Draft failed unexpectedly: {exc}"[:300]})
        time.sleep(settings.research_delay_seconds)
