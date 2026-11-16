import time

from supabase import Client, create_client

from app.config import settings

supabase: Client = create_client(settings.supabase_url, settings.supabase_service_key)


def with_retry(fn, attempts: int = 3, delay: float = 1.0):
    """Run a DB call, retrying briefly so a slow first request after idle doesn't surface as an error."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(delay * (i + 1))
    raise last  # type: ignore[misc]
