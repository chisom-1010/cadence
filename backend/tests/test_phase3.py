from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import current_user
from app.llm import LLMError
from app.main import app
from app.schemas import DraftOut, ICP, ReplyClass
from app.services import drafting, replies as replies_service, sending

GOOD_BODY = ("Hi Amara, congratulations on opening the Lome hub. We help freight teams plan routes automatically so trucks "
             "return full and deliveries arrive on time. If that is a priority for Brightline, could we talk for fifteen "
             "minutes this week? If this is not relevant, tell me and I will not follow up.")


def draft_ok(*a, **k):
    return DraftOut(subject="Fewer empty return trips", body=GOOD_BODY)


@pytest.fixture
def client(fake):
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u1", email="a@b.co")
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def setup(fake, monkeypatch):
    """A campaign with one researched lead (fit 80) and one weak lead (fit 20)."""
    monkeypatch.setattr(drafting, "complete_json", draft_ok)
    monkeypatch.setattr(drafting.settings, "research_delay_seconds", 0)
    monkeypatch.setattr(drafting.settings, "sender_name", "Outreach")      # tests must not depend on the developer's .env
    monkeypatch.setattr(drafting.settings, "min_fit_to_draft", 40)
    monkeypatch.setattr(sending.settings, "send_delay_seconds", 0)
    monkeypatch.setattr(sending.settings, "demo_recipient", "me@demo.test")
    monkeypatch.setattr(sending.settings, "live_sending", False)
    sent = []
    monkeypatch.setattr(sending, "send_email", lambda to, subject, body: sent.append((to, subject)) or "me@demo.test")
    c = fake.create_campaign("u1", {"name": "T", "product_pitch": "Route planning", "icp": ICP(summary="s", pain_points=["empty trips"]).model_dump()})
    fake.insert_leads("u1", c["id"], [
        {"company_name": "Brightline", "domain": "brightline.example", "contact_name": "Amara", "contact_email": "amara@brightline.example"},
        {"company_name": "Weak Co", "domain": "weak.example"},
    ])
    ids = list(fake.leads)
    fake.update_lead("u1", ids[0], {"status": "researched", "fit_score": 80, "research_summary": "Freight firm", "personalization_hook": "Lome hub"})
    fake.update_lead("u1", ids[1], {"status": "researched", "fit_score": 20, "research_summary": "Tiny"})
    return SimpleNamespace(cid=c["id"], good=ids[0], weak=ids[1], sent=sent)


def test_draft_schema_rejects_placeholders_and_wrong_length():
    with pytest.raises(ValueError):
        DraftOut(subject="Hello [Name]", body=GOOD_BODY)
    with pytest.raises(ValueError):
        DraftOut(subject="Hello", body="Too short.")
    with pytest.raises(ValueError):
        DraftOut(subject="Hello", body=GOOD_BODY + " Regards, [Your Name]")


def test_campaign_draft_only_drafts_leads_above_the_fit_threshold(client, setup, fake):
    r = client.post(f"/campaigns/{setup.cid}/draft")
    assert r.json() == {"queued": 1, "min_fit": 40}
    emails = list(fake.emails.values())
    assert len(emails) == 1 and emails[0]["lead_id"] == setup.good and emails[0]["status"] == "draft"
    assert emails[0]["body"].endswith("Outreach")           # signature added in code, not by the model
    assert fake.leads[setup.good]["status"] == "drafted" and fake.leads[setup.weak]["status"] == "researched"


def test_background_draft_records_a_failure_on_the_lead_and_continues(client, setup, fake, monkeypatch):
    calls = []
    def flaky(*a, **k):
        calls.append(1)
        raise LLMError("rate limited")
    monkeypatch.setattr(drafting, "complete_json", flaky)
    assert client.post(f"/campaigns/{setup.cid}/draft").json()["queued"] == 1
    assert "Draft failed" in fake.leads[setup.good]["error"] and not fake.emails


def test_single_draft_needs_research_and_maps_llm_errors(client, setup, fake, monkeypatch):
    fake.update_lead("u1", setup.good, {"status": "new"})
    assert client.post(f"/leads/{setup.good}/draft").status_code == 409
    fake.update_lead("u1", setup.good, {"status": "researched"})
    monkeypatch.setattr(drafting, "complete_json", lambda *a, **k: (_ for _ in ()).throw(LLMError("no key")))
    assert client.post(f"/leads/{setup.good}/draft").status_code == 502
    monkeypatch.setattr(drafting, "complete_json", draft_ok)
    assert client.post(f"/leads/{setup.good}/draft").status_code == 200


def test_redraft_reuses_the_row_but_not_after_approval(client, setup, fake):
    eid = client.post(f"/leads/{setup.good}/draft").json()["email"]["id"]
    assert client.post(f"/leads/{setup.good}/draft").json()["email"]["id"] == eid and len(fake.emails) == 1
    client.post(f"/emails/{eid}/approve")
    assert client.post(f"/leads/{setup.good}/draft").status_code == 409


def test_edit_approve_reject_flow_and_lead_status(client, setup, fake):
    eid = client.post(f"/leads/{setup.good}/draft").json()["email"]["id"]
    assert client.patch(f"/emails/{eid}", json={"subject": "New subject"}).json()["email"]["subject"] == "New subject"
    assert client.patch(f"/emails/{eid}", json={}).status_code == 422
    assert client.patch(f"/emails/{eid}", json={"body": "   "}).status_code == 422
    assert client.post(f"/emails/{eid}/approve").json()["email"]["status"] == "approved"
    assert fake.leads[setup.good]["status"] == "approved"
    assert client.post(f"/emails/{eid}/approve").status_code == 409          # already approved
    # editing an approved email sends it back for re-approval
    assert client.patch(f"/emails/{eid}", json={"body": "Changed text"}).json()["email"]["status"] == "draft"
    assert client.post(f"/emails/{eid}/reject").json()["email"]["status"] == "rejected"
    assert fake.leads[setup.good]["status"] == "researched"
    assert client.patch(f"/emails/{eid}", json={"subject": "x"}).status_code == 409   # rejected is final until redrafted


def test_send_requires_approval_and_never_sends_twice(client, setup, fake):
    eid = client.post(f"/leads/{setup.good}/draft").json()["email"]["id"]
    assert client.post(f"/emails/{eid}/send").status_code == 409             # still a draft
    assert setup.sent == []
    client.post(f"/emails/{eid}/approve")
    out = client.post(f"/emails/{eid}/send").json()["email"]
    assert out["status"] == "sent" and out["sent_to"] == "me@demo.test"
    assert setup.sent == [("me@demo.test", "Fewer empty return trips")]   # demo mode: the lead is never contacted
    assert client.post(f"/emails/{eid}/send").status_code == 409             # second click does nothing
    assert len(setup.sent) == 1 and fake.leads[setup.good]["status"] == "sent"


def test_provider_failure_marks_the_email_failed_and_allows_retry(client, setup, fake, monkeypatch):
    eid = client.post(f"/leads/{setup.good}/draft").json()["email"]["id"]
    client.post(f"/emails/{eid}/approve")
    def boom(*a, **k):
        raise RuntimeError("Unauthorized")
    monkeypatch.setattr(sending, "send_email", boom)
    r = client.post(f"/emails/{eid}/send")
    assert r.status_code == 502 and "Unauthorized" in r.json()["detail"]
    assert fake.emails[eid]["status"] == "failed" and fake.leads[setup.good]["status"] == "approved"
    monkeypatch.setattr(sending, "send_email", lambda *a, **k: "me@demo.test")
    assert client.post(f"/emails/{eid}/approve").status_code == 200           # approve again, then send
    assert client.post(f"/emails/{eid}/send").json()["email"]["status"] == "sent"


def test_with_live_sending_a_lead_without_an_address_fails_cleanly(client, setup, fake, monkeypatch):
    monkeypatch.setattr(sending.settings, "demo_recipient", "")
    monkeypatch.setattr(sending.settings, "live_sending", True)
    fake.update_lead("u1", setup.weak, {"status": "researched", "fit_score": 90})
    eid = client.post(f"/leads/{setup.weak}/draft").json()["email"]["id"]
    client.post(f"/emails/{eid}/approve")
    r = client.post(f"/emails/{eid}/send")
    assert r.status_code == 502 and "no email address" in r.json()["detail"] and setup.sent == []


def test_bulk_approve_and_send(client, setup, fake):
    fake.update_lead("u1", setup.weak, {"fit_score": 90})
    assert client.post(f"/campaigns/{setup.cid}/draft").json()["queued"] == 2
    assert client.post("/emails/approve-all").json() == {"approved": 2}
    assert client.post("/emails/send-approved").json() == {"queued": 2}
    assert {e["status"] for e in fake.emails.values()} == {"sent"} and len(setup.sent) == 2


def test_other_users_cannot_touch_my_emails_or_leads(client, setup, fake):
    eid = client.post(f"/leads/{setup.good}/draft").json()["email"]["id"]
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u2", email="x@y.co")
    for method, path in [("post", f"/emails/{eid}/approve"), ("post", f"/emails/{eid}/send"), ("post", f"/emails/{eid}/reject"),
                         ("post", f"/leads/{setup.good}/draft"), ("post", f"/leads/{setup.good}/replies/simulate")]:
        assert getattr(client, method)(path, json={}).status_code == 404, path
    assert client.patch(f"/emails/{eid}", json={"subject": "x"}).status_code == 404
    assert client.post("/emails/approve-all").json() == {"approved": 0}


def test_requests_without_a_token_are_rejected(fake):
    app.dependency_overrides.clear()
    c = TestClient(app)
    for path in ["/emails/approve-all", "/emails/send-approved", "/emails/x/send", "/leads/x/draft", "/leads/x/replies", "/replies/x/classify"]:
        assert c.post(path, json={}).status_code == 401, path
    assert c.patch("/emails/x", json={}).status_code == 401


# ---------- replies ----------
def sent_lead(client, setup):
    eid = client.post(f"/leads/{setup.good}/draft").json()["email"]["id"]
    client.post(f"/emails/{eid}/approve")
    client.post(f"/emails/{eid}/send")
    return eid


def test_reply_needs_a_sent_email(client, setup):
    assert client.post(f"/leads/{setup.good}/replies/simulate", json={"sample": "interested"}).status_code == 409


def test_simulated_reply_is_labelled_and_flags_hot(client, setup, fake, monkeypatch):
    eid = sent_lead(client, setup)
    monkeypatch.setattr(replies_service, "complete_json", lambda *a, **k: ReplyClass(label="interested", is_hot=True, reason="Asks for pricing and a call"))
    out = client.post(f"/leads/{setup.good}/replies/simulate", json={"sample": "interested"}).json()
    assert out["warning"] is None
    r = out["reply"]
    assert r["label"] == "interested" and r["is_hot"] is True and r["simulated"] is True and r["email_id"] == eid
    assert fake.leads[setup.good]["status"] == "replied"


def test_hot_is_forced_off_for_negative_labels(client, setup, monkeypatch):
    sent_lead(client, setup)
    monkeypatch.setattr(replies_service, "complete_json", lambda *a, **k: ReplyClass(label="not_interested", is_hot=True, reason="No"))
    assert client.post(f"/leads/{setup.good}/replies", json={"body": "No thanks"}).json()["reply"]["is_hot"] is False


def test_reply_is_saved_even_when_the_llm_fails_and_can_be_relabelled(client, setup, fake, monkeypatch):
    sent_lead(client, setup)
    monkeypatch.setattr(replies_service, "complete_json", lambda *a, **k: (_ for _ in ()).throw(LLMError("down")))
    out = client.post(f"/leads/{setup.good}/replies", json={"body": "Sounds good, call me"}).json()
    assert out["warning"] and out["reply"]["label"] is None and out["reply"]["simulated"] is False
    rid = out["reply"]["id"]
    assert client.post(f"/replies/{rid}/classify").status_code == 502
    monkeypatch.setattr(replies_service, "complete_json", lambda *a, **k: ReplyClass(label="interested", is_hot=True, reason="Wants a call"))
    assert client.post(f"/replies/{rid}/classify").json()["reply"]["label"] == "interested"
    assert client.post("/replies/nope/classify").status_code == 404


def test_empty_reply_body_is_rejected(client, setup):
    sent_lead(client, setup)
    assert client.post(f"/leads/{setup.good}/replies", json={"body": ""}).status_code == 422


# ---- Delivery rules: demo mode only ever delivers to the confirmed account owner ----

def _approved(client, setup):
    eid = client.post(f"/leads/{setup.good}/draft").json()["email"]["id"]
    client.post(f"/emails/{eid}/approve")
    return eid


def test_demo_mode_delivers_to_the_confirmed_owner_with_a_disclosure(client, setup, monkeypatch):
    monkeypatch.setattr(sending.settings, "demo_recipient", "")
    monkeypatch.setattr(sending.settings, "live_sending", False)
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u1", email="owner@me.co", email_confirmed_at="2026-11-01")
    bodies = []
    monkeypatch.setattr(sending, "send_email", lambda to, subject, body: bodies.append((to, body)) or to)
    eid = _approved(client, setup)
    out = client.post(f"/emails/{eid}/send").json()["email"]
    assert out["sent_to"] == "owner@me.co"
    assert bodies[0][0] == "owner@me.co" and bodies[0][1].startswith("[Cadance demo]") and "amara@brightline.example" in bodies[0][1]


def test_demo_mode_refuses_an_unconfirmed_owner_and_keeps_the_email_approved(client, setup, fake, monkeypatch):
    monkeypatch.setattr(sending.settings, "demo_recipient", "")
    monkeypatch.setattr(sending.settings, "live_sending", False)
    eid = _approved(client, setup)                                   # default test user has no email_confirmed_at
    r = client.post(f"/emails/{eid}/send")
    assert r.status_code == 403 and "not confirmed" in r.json()["detail"]
    assert fake.emails[eid]["status"] == "approved" and setup.sent == []
    assert client.post("/emails/send-approved").status_code == 403


def test_live_sending_goes_to_the_lead(client, setup, monkeypatch):
    monkeypatch.setattr(sending.settings, "demo_recipient", "")
    monkeypatch.setattr(sending.settings, "live_sending", True)
    got = []
    monkeypatch.setattr(sending, "send_email", lambda to, subject, body: got.append((to, body)) or to)
    eid = _approved(client, setup)
    assert client.post(f"/emails/{eid}/send").json()["email"]["sent_to"] == "amara@brightline.example"
    assert not got[0][1].startswith("[Cadance demo]")
