"""All outgoing email goes through send_email(). Swap providers by editing only this file."""
import mailtrap as mt

from app.config import settings

_client: mt.MailtrapClient | None = None


def _get_client() -> mt.MailtrapClient:
    global _client
    if _client is None:
        if not settings.mailtrap_api_token:
            raise RuntimeError("MAILTRAP_API_TOKEN is not set")
        _client = mt.MailtrapClient(token=settings.mailtrap_api_token)
    return _client


def send_email(to: str, subject: str, body: str) -> str:
    """Send one email. Returns the address it was actually delivered to (differs in demo mode)."""
    if not settings.sender_email:
        raise RuntimeError("SENDER_EMAIL is not set on the server.")
    actual_to = settings.demo_recipient or to
    if settings.demo_recipient:
        body = f"[DEMO MODE: originally for {to}]\n\n{body}"
    mail = mt.Mail(
        sender=mt.Address(email=settings.sender_email, name=settings.sender_name),
        to=[mt.Address(email=actual_to)],
        subject=subject,
        text=body,
    )
    _get_client().send(mail)
    return actual_to
