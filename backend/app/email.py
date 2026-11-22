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
    """Send one email to exactly `to`. Who `to` is gets decided in services/sending.py."""
    if not settings.sender_email:
        raise RuntimeError("SENDER_EMAIL is not set on the server.")
    mail = mt.Mail(
        sender=mt.Address(email=settings.sender_email, name=settings.sender_name),
        to=[mt.Address(email=to)],
        subject=subject,
        text=body,
    )
    _get_client().send(mail)
    return to
