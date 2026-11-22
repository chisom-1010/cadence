from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app import repo
from app.auth import current_user
from app.config import settings
from app.llm import LLMError
from app.schemas import EmailEdit
from app.services import drafting, sending

router = APIRouter(tags=["emails"])


def _campaign_or_404(user, campaign_id: str) -> dict:
    c = repo.get_campaign(user.id, campaign_id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    return c


def _email_or_404(user, email_id: str) -> dict:
    e = repo.get_email(user.id, email_id)
    if not e:
        raise HTTPException(404, "Email not found")
    return e


def _set_lead(user, email: dict, status: str) -> None:
    repo.update_lead(user.id, email["lead_id"], {"status": status})


@router.post("/campaigns/{campaign_id}/draft")
def draft_campaign(campaign_id: str, background: BackgroundTasks, user=Depends(current_user)):
    """Queue drafts for researched leads whose fit score is high enough."""
    campaign = _campaign_or_404(user, campaign_id)
    ids = [l["id"] for l in repo.list_leads(user.id, campaign_id, ["researched"])
           if (l.get("fit_score") or 0) >= settings.min_fit_to_draft]
    if ids:
        background.add_task(drafting.draft_many, user.id, campaign, ids)
    return {"queued": len(ids), "min_fit": settings.min_fit_to_draft}


@router.post("/leads/{lead_id}/draft")
def draft_one(lead_id: str, user=Depends(current_user)):
    """Write (or rewrite) the draft for one lead right now."""
    lead = repo.get_lead(user.id, lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    if lead["status"] not in ("researched", "drafted"):
        raise HTTPException(409, "Research this lead before drafting an email.")
    campaign = _campaign_or_404(user, lead["campaign_id"])
    try:
        return {"email": drafting.draft_lead(user.id, campaign, lead)}
    except drafting.DraftBlocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.patch("/emails/{email_id}")
def edit_email(email_id: str, body: EmailEdit, user=Depends(current_user)):
    """Edit a draft. Editing an approved email sends it back to draft so it must be approved again."""
    email = _email_or_404(user, email_id)
    changes = {k: v.strip() for k, v in body.model_dump(exclude_none=True).items()}
    if not changes or any(not v for v in changes.values()):
        raise HTTPException(422, "Subject and body cannot be empty.")
    updated = repo.transition_email(user.id, email_id, ["draft", "approved"], {**changes, "status": "draft", "approved_at": None})
    if updated is None:
        raise HTTPException(409, f"This email is {email['status']} and can no longer be edited.")
    _set_lead(user, email, "drafted")
    return {"email": updated}


@router.post("/emails/{email_id}/approve")
def approve_email(email_id: str, user=Depends(current_user)):
    from datetime import datetime, timezone
    email = _email_or_404(user, email_id)
    updated = repo.transition_email(user.id, email_id, ["draft", "failed"],
                                    {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat(), "error": None})
    if updated is None:
        raise HTTPException(409, f"This email is {email['status']} and cannot be approved.")
    _set_lead(user, email, "approved")
    return {"email": updated}


@router.post("/emails/{email_id}/reject")
def reject_email(email_id: str, user=Depends(current_user)):
    email = _email_or_404(user, email_id)
    updated = repo.transition_email(user.id, email_id, ["draft", "approved", "failed"], {"status": "rejected", "approved_at": None})
    if updated is None:
        raise HTTPException(409, f"This email is {email['status']} and cannot be rejected.")
    _set_lead(user, email, "researched")
    return {"email": updated}


@router.post("/emails/approve-all")
def approve_all(user=Depends(current_user)):
    from datetime import datetime, timezone
    n = 0
    for e in repo.list_emails(user.id, ["draft"]):
        if repo.transition_email(user.id, e["id"], ["draft"], {"status": "approved", "approved_at": datetime.now(timezone.utc).isoformat(), "error": None}):
            _set_lead(user, e, "approved")
            n += 1
    return {"approved": n}


def _owner(user) -> tuple[str | None, bool]:
    """The signed-in user's address, and whether Supabase has confirmed they own it."""
    return user.email, bool(getattr(user, "email_confirmed_at", None))


@router.post("/emails/send-approved")
def send_approved(background: BackgroundTasks, user=Depends(current_user)):
    """Send every approved email in the background, one at a time."""
    ids = [e["id"] for e in repo.list_emails(user.id, ["approved"])]
    owner_email, confirmed = _owner(user)
    try:
        sending.recipient_for(None, owner_email, confirmed)       # fail now, not silently in the background
    except sending.DeliveryBlocked as exc:
        raise HTTPException(403, str(exc)) from exc
    if ids:
        background.add_task(sending.send_many, user.id, ids, owner_email, confirmed)
    return {"queued": len(ids)}


@router.post("/emails/{email_id}/send")
def send_email_now(email_id: str, user=Depends(current_user)):
    _email_or_404(user, email_id)
    try:
        email = sending.send_one(user.id, email_id, *_owner(user))
    except sending.SendBlocked as exc:
        raise HTTPException(409, str(exc)) from exc
    except sending.DeliveryBlocked as exc:
        raise HTTPException(403, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    if email["status"] == "failed":
        raise HTTPException(502, email.get("error") or "Sending failed.")
    return {"email": email}
