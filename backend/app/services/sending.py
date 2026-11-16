"""Send approved emails. An email is claimed (approved -> sent) before the provider is called, so a
double click or two overlapping jobs can never send it twice. If the provider fails it is marked failed."""
import time
from datetime import datetime, timezone

from app import repo
from app.config import settings
from app.email import send_email


class SendBlocked(Exception):
    """The email is not in the approved state."""


def send_one(user_id: str, email_id: str) -> dict:
    """Returns the email row, with status 'sent' or 'failed'. Raises LookupError / SendBlocked."""
    email = repo.get_email(user_id, email_id)
    if not email:
        raise LookupError("Email not found")
    lead = repo.get_lead(user_id, email["lead_id"])
    if not lead:
        raise LookupError("Lead not found")

    claimed = repo.transition_email(user_id, email_id, ["approved"],
                                    {"status": "sent", "sent_at": datetime.now(timezone.utc).isoformat(), "error": None})
    if claimed is None:
        raise SendBlocked("Only approved emails can be sent.")

    to = lead.get("contact_email") or (f"contact@{lead['domain']}" if lead.get("domain") else None)
    problem = None
    if not lead.get("contact_email") and not settings.demo_recipient:
        problem = "This lead has no email address. Import one with a CSV, or turn on demo mode."
    elif not to:
        problem = "This lead has no email address or domain."
    if problem is None:
        try:
            actual_to = send_email(to, email["subject"], email["body"])
        except Exception as exc:  # noqa: BLE001  the mail SDK raises several kinds of error
            problem = f"Sending failed: {exc}"[:300]
    if problem:
        return repo.transition_email(user_id, email_id, ["sent"], {"status": "failed", "error": problem, "sent_at": None}) or claimed

    sent = repo.transition_email(user_id, email_id, ["sent"], {"sent_to": actual_to}) or claimed
    repo.update_lead(user_id, lead["id"], {"status": "sent"})
    return sent


def send_many(user_id: str, email_ids: list[str]) -> None:
    for email_id in email_ids:
        try:
            send_one(user_id, email_id)
        except (LookupError, SendBlocked):
            pass
        except Exception as exc:  # noqa: BLE001
            repo.transition_email(user_id, email_id, ["sent"], {"status": "failed", "error": f"Unexpected error: {exc}"[:300]})
        time.sleep(settings.send_delay_seconds)
