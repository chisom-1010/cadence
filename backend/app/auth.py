from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import supabase

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """Validate the Supabase access token sent by the Next.js client and return the user."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        res = supabase.auth.get_user(creds.credentials)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    if res is None or res.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return res.user
