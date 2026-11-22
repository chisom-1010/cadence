"""Send approved emails. An email is claimed (approved -> sent) before the provider is called, so a
double click or two overlapping jobs can never send it twice. If the provider fails it is marked failed."""
import time
from datetime import datetime, timezone

from app import repo
from app.config import settings
from app.email import send_email


class SendBlocked(Exception):
    """The email is not in the approved state."""


class DeliveryBlocked(Exception):
    """Demo mode is on and there is no confirmed address to deliver to."""


DEMO_NOTE = ("[Cadance demo] This email was drafted for {to}. It was delivered only to you, "
             "because Cadance sends to the signed-in account owner unless live sending is switched on.\n\n")


def recipient_for(lead_to: str | None, owner_email: str | None, owner_confirmed: bool) -> tuple[str | None, bool]:
    """Decide who really receives the email. Returns (address, is_demo).
    Live sending: the lead. Otherwise DEMO_RECIPIENT, or the signed-in owner once their email is confirmed."""
    if settings.live_sending:
        return lead_to, False
    if settings.demo_recipient:
        return settings.demo_recipient, True
    if owner_email and owner_confirmed:
        return owner_email, True
    raise DeliveryBlocked("Demo mode delivers only to your own email address, and yours is not confirmed yet. "
                          "Confirm it from the link Supabase emailed you, then try again.")


def send_one(user_id: str, email_id: str, owner_email: str | None = None, owner_confirmed: bool = False) -> dict:
    """Returns the email row, with status 'sent' or 'failed'. Raises LookupError / SendBlocked."""
    email = repo.get_email(user_id, email_id)
    if not email:
        raise LookupError("Email not found")
    lead = repo.get_lead(user_id, email["lead_id"])
    if not lead:
        raise LookupError("Lead not found")

    lead_to = lead.get("contact_email") or (f"contact@{lead['domain']}" if lead.get("domain") else None)
    target, demo = recipient_for(lead_to, owner_email, owner_confirmed)   # may raise DeliveryBlocked: nothing is claimed yet

    claimed = repo.transition_email(user_id, email_id, ["approved"],
                                    {"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat(), "error": None})
    if claimed is None:
        raise SendBlocked("Only approved emails can be sent.")

    problem = None
    if not demo and not lead.get("contact_email"):
        problem = "This lead has no email address. Import one with a CSV, or turn on demo mode."
    elif not target:
        problem = "This lead has no email address or domain."
    if problem is None:
        body = DEMO_NOTE.format(to=lead_to or lead["company_name"]) + email["body"] if demo else email["body"]
        try:
            actual_to = send_email(target, email["subject"], body)
        except Exception as exc:  # noqa: BLE001  the mail SDK raises several kinds of error
            problem = f"Sending failed: {exc}"[:300]
    if problem:
        return repo.transition_email(user_id, email_id, ["sent"], {"status": "failed", "error": problem, "sent_at": None}) or claimed

    sent = repo.transition_email(user_id, email_id, ["sent"], {"sent_to": actual_to}) or claimed
    repo.update_lead(user_id, lead["id"], {"status": "sent"})
    return sent


def send_many(user_id: str, email_ids: list[str], owner_email: str | None = None, owner_confirmed: bool = False) -> None:
    for email_id in email_ids:
        try:
            send_one(user_id, email_id, owner_email, owner_confirmed)
        except (LookupError, SendBlocked, DeliveryBlocked):
            pass
        except Exception as exc:  # noqa: BLE001
            repo.transition_email(user_id, email_id, ["sent"], {"status": "failed", "error": f"Unexpected error: {exc}"[:300]})
        time.sleep(settings.send_delay_seconds)
