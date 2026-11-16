from fastapi import APIRouter, Depends, HTTPException

from app import repo
from app.auth import current_user
from app.schemas import ReplyIn, SimulateIn
from app.services import replies as replies_service

router = APIRouter(tags=["replies"])


def _lead_with_email_or_error(user, lead_id: str) -> dict:
    lead = repo.get_lead(user.id, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead["status"] not in ("sent", "replied"):
        raise HTTPException(409, "Only leads that were sent an email can have a reply.")
    return lead


@router.post("/leads/{lead_id}/replies/simulate")
def simulate_reply(lead_id: str, body: SimulateIn, user=Depends(current_user)):
    """Demo helper: add a realistic canned reply, then label it with the LLM exactly like a real one."""
    lead = _lead_with_email_or_error(user, lead_id)
    reply, warning = replies_service.record_reply(user.id, lead, replies_service.SAMPLES[body.sample], simulated=True)
    return {"reply": reply, "warning": warning}


@router.post("/leads/{lead_id}/replies")
def log_reply(lead_id: str, body: ReplyIn, user=Depends(current_user)):
    """Paste a real reply you received so it is labelled and tracked."""
    lead = _lead_with_email_or_error(user, lead_id)
    reply, warning = replies_service.record_reply(user.id, lead, body.body, simulated=False)
    return {"reply": reply, "warning": warning}


@router.post("/replies/{reply_id}/classify")
def reclassify(reply_id: str, user=Depends(current_user)):
    """Retry labelling, for a reply saved while the LLM was unavailable."""
    reply = repo.get_reply(user.id, reply_id)
    if not reply:
        raise HTTPException(404, "Reply not found")
    fields, warning = replies_service.label_fields(reply["body"])
    if warning:
        raise HTTPException(502, warning)
    return {"reply": repo.update_reply(user.id, reply_id, fields)}
