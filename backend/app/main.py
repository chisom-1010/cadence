from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import supabase, with_retry
from app.routers import campaigns, emails, me, people, replies

app = FastAPI(title="Explee Clone API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router)
app.include_router(campaigns.router)
app.include_router(emails.router)
app.include_router(replies.router)
app.include_router(people.router)


@app.get("/health")
def health():
    """Ping target for the cron job. Runs a trivial query so the Supabase connection stays warm."""
    with_retry(lambda: supabase.table("campaigns").select("id").limit(1).execute())
    return {"status": "ok"}
