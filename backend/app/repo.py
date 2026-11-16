"""All database access. Every function takes user_id and filters by it, because the server
uses the service key, which bypasses row level security."""
from app.db import supabase, with_retry


def _first(res):
    return res.data[0] if res.data else None


def create_campaign(user_id: str, fields: dict) -> dict:
    res = with_retry(lambda: supabase.table("campaigns").insert({**fields, "user_id": user_id}).execute())
    return _first(res)


def get_campaign(user_id: str, campaign_id: str) -> dict | None:
    res = with_retry(lambda: supabase.table("campaigns").select("*").eq("id", campaign_id).eq("user_id", user_id).limit(1).execute())
    return _first(res)


def update_campaign(user_id: str, campaign_id: str, fields: dict) -> dict | None:
    res = with_retry(lambda: supabase.table("campaigns").update(fields).eq("id", campaign_id).eq("user_id", user_id).execute())
    return _first(res)


def get_lead(user_id: str, lead_id: str) -> dict | None:
    res = with_retry(lambda: supabase.table("leads").select("*").eq("id", lead_id).eq("user_id", user_id).limit(1).execute())
    return _first(res)


def list_leads(user_id: str, campaign_id: str, statuses: list[str] | None = None) -> list[dict]:
    def q():
        query = supabase.table("leads").select("*").eq("campaign_id", campaign_id).eq("user_id", user_id)
        if statuses:
            query = query.in_("status", statuses)
        return query.order("created_at").execute()
    return with_retry(q).data or []


def existing_domains(user_id: str, campaign_id: str) -> set[str]:
    res = with_retry(lambda: supabase.table("leads").select("domain").eq("campaign_id", campaign_id).eq("user_id", user_id).execute())
    return {r["domain"] for r in (res.data or []) if r.get("domain")}


def insert_leads(user_id: str, campaign_id: str, rows: list[dict]) -> int:
    """Insert leads, silently skipping domains already in the campaign. Returns how many were added."""
    if not rows:
        return 0
    payload = [{**r, "user_id": user_id, "campaign_id": campaign_id} for r in rows]
    res = with_retry(lambda: supabase.table("leads").upsert(payload, on_conflict="campaign_id,domain", ignore_duplicates=True).execute())
    return len(res.data or [])


def claim_lead(user_id: str, lead_id: str, from_statuses: list[str]) -> dict | None:
    """Move a lead to 'researching' only if it is still in one of from_statuses. Prevents double processing."""
    res = with_retry(lambda: supabase.table("leads").update({"status": "researching", "error": None})
                     .eq("id", lead_id).eq("user_id", user_id).in_("status", from_statuses).execute())
    return _first(res)


def update_lead(user_id: str, lead_id: str, fields: dict) -> dict | None:
    res = with_retry(lambda: supabase.table("leads").update(fields).eq("id", lead_id).eq("user_id", user_id).execute())
    return _first(res)


# ---------- emails ----------
def get_email(user_id: str, email_id: str) -> dict | None:
    res = with_retry(lambda: supabase.table("emails").select("*").eq("id", email_id).eq("user_id", user_id).limit(1).execute())
    return _first(res)


def get_latest_email(user_id: str, lead_id: str) -> dict | None:
    res = with_retry(lambda: supabase.table("emails").select("*").eq("lead_id", lead_id).eq("user_id", user_id)
                     .order("created_at", desc=True).limit(1).execute())
    return _first(res)


def list_emails(user_id: str, statuses: list[str] | None = None, campaign_id: str | None = None) -> list[dict]:
    def q():
        query = supabase.table("emails").select("*").eq("user_id", user_id)
        if statuses:
            query = query.in_("status", statuses)
        if campaign_id:
            query = query.eq("campaign_id", campaign_id)
        return query.order("created_at").execute()
    return with_retry(q).data or []


def insert_email(user_id: str, fields: dict) -> dict:
    res = with_retry(lambda: supabase.table("emails").insert({**fields, "user_id": user_id}).execute())
    return _first(res)


def transition_email(user_id: str, email_id: str, from_statuses: list[str], fields: dict) -> dict | None:
    """Update an email only if it is still in one of from_statuses. Returns None when the state has
    already moved on, which is how double clicks and double sends are stopped."""
    res = with_retry(lambda: supabase.table("emails").update(fields).eq("id", email_id).eq("user_id", user_id)
                     .in_("status", from_statuses).execute())
    return _first(res)


# ---------- replies ----------
def get_reply(user_id: str, reply_id: str) -> dict | None:
    res = with_retry(lambda: supabase.table("replies").select("*").eq("id", reply_id).eq("user_id", user_id).limit(1).execute())
    return _first(res)


def insert_reply(user_id: str, fields: dict) -> dict:
    res = with_retry(lambda: supabase.table("replies").insert({**fields, "user_id": user_id}).execute())
    return _first(res)


def update_reply(user_id: str, reply_id: str, fields: dict) -> dict | None:
    res = with_retry(lambda: supabase.table("replies").update(fields).eq("id", reply_id).eq("user_id", user_id).execute())
    return _first(res)


# ---------- contacts (people found for a lead) ----------
def list_contacts(user_id: str, lead_id: str) -> list[dict]:
    res = with_retry(lambda: supabase.table("contacts").select("*").eq("lead_id", lead_id).eq("user_id", user_id).order("created_at").execute())
    return res.data or []


def get_contact(user_id: str, contact_id: str) -> dict | None:
    res = with_retry(lambda: supabase.table("contacts").select("*").eq("id", contact_id).eq("user_id", user_id).limit(1).execute())
    return _first(res)


def lead_ids_with_contacts(user_id: str, campaign_id: str) -> set[str]:
    res = with_retry(lambda: supabase.table("contacts").select("lead_id").eq("campaign_id", campaign_id).eq("user_id", user_id).execute())
    return {r["lead_id"] for r in (res.data or [])}


def replace_contacts(user_id: str, lead: dict, rows: list[dict]) -> list[dict]:
    """Swap a lead's contacts for a fresh set. Not atomic, but a failed insert only leaves the lead without people."""
    with_retry(lambda: supabase.table("contacts").delete().eq("lead_id", lead["id"]).eq("user_id", user_id).execute())
    if not rows:
        return []
    payload = [{**r, "user_id": user_id, "lead_id": lead["id"], "campaign_id": lead["campaign_id"]} for r in rows]
    return with_retry(lambda: supabase.table("contacts").insert(payload).execute()).data or []


def set_primary_contact(user_id: str, lead_id: str, contact_id: str) -> None:
    with_retry(lambda: supabase.table("contacts").update({"is_primary": False}).eq("lead_id", lead_id).eq("user_id", user_id).execute())
    with_retry(lambda: supabase.table("contacts").update({"is_primary": True}).eq("id", contact_id).eq("user_id", user_id).execute())
