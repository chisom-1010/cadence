from fastapi import APIRouter, Depends

from app.auth import current_user
from app.config import settings

router = APIRouter(tags=["auth"])


@router.get("/me")
def me(user=Depends(current_user)):
    """Smoke test for auth, plus the mail settings the client needs to explain what Send will do."""
    return {
        "id": user.id,
        "email": user.email,
        "demo_mode": bool(settings.demo_recipient),
        "demo_recipient": settings.demo_recipient or None,
        "mail_configured": bool(settings.mailtrap_api_token and settings.sender_email),
    }
