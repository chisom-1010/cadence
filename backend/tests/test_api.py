from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import current_user
from app.llm import LLMError
from app.main import app
from app.schemas import ICP, ResearchOut
from app.search import SearchError
from app.services import discovery, icp as icp_service, research

LONG = "Acme Freight moves pallets across the region. " * 20
GOOD_ICP = ICP(summary="Small logistics firms", industries=["logistics"])


@pytest.fixture
def client(fake):
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u1", email="a@b.co")
    yield TestClient(app)
    app.dependency_overrides.clear()


def mk(client, monkeypatch, icp=GOOD_ICP):
    monkeypatch.setattr(icp_service, "complete_json", lambda *a, **k: icp)
    r = client.post("/campaigns", json={"name": "Test", "product_pitch": "p", "icp_description": "small logistics firms"})
    assert r.status_code == 200
    return r.json()


def test_requests_without_a_token_are_rejected(fake):
    app.dependency_overrides.clear()
    c = TestClient(app)
    for method, path in [("post", "/campaigns"), ("post", "/campaigns/x/discover"), ("post", "/leads/x/research"), ("get", "/me")]:
        assert getattr(c, method)(path, **({"json": {}} if method == "post" else {})).status_code == 401


def test_create_campaign_parses_the_icp(client, monkeypatch, fake):
    out = mk(client, monkeypatch)
    assert out["warning"] is None and out["campaign"]["icp"]["industries"] == ["logistics"]
    assert fake.campaigns[out["campaign"]["id"]]["user_id"] == "u1"


def test_create_campaign_keeps_the_campaign_when_the_llm_fails(client, monkeypatch, fake):
    def boom(*a, **k):
        raise LLMError("LLM_API_KEY is not set on the server.")
    monkeypatch.setattr(icp_service, "complete_json", boom)
    out = client.post("/campaigns", json={"name": "T", "icp_description": "small logistics firms"}).json()
    assert out["campaign"]["icp"] is None and "LLM_API_KEY" in out["warning"]
    cid = out["campaign"]["id"]
    assert client.post(f"/campaigns/{cid}/discover").status_code == 409           # needs an ICP first
    assert client.post(f"/campaigns/{cid}/research").status_code == 409
    monkeypatch.setattr(icp_service, "complete_json", lambda *a, **k: GOOD_ICP)   # provider is back
    assert client.post(f"/campaigns/{cid}/icp").json()["campaign"]["icp"]["summary"] == "Small logistics firms"


def test_validation_rejects_empty_input(client):
    assert client.post("/campaigns", json={"name": "", "icp_description": "x"}).status_code == 422
    assert client.post("/campaigns", json={"name": "ok", "icp_description": "x"}).status_code == 422


def test_other_users_campaigns_look_like_they_do_not_exist(client, monkeypatch, fake):
    theirs = fake.create_campaign("u2", {"name": "secret", "icp": GOOD_ICP.model_dump()})
    for path in ["/discover", "/seed", "/research", "/icp"]:
        assert client.post(f"/campaigns/{theirs['id']}{path}").status_code == 404, path
    assert client.post(f"/campaigns/{theirs['id']}/leads/import", json={"csv": "company\nx"}).status_code == 404
    fake.insert_leads("u2", theirs["id"], [{"company_name": "X", "domain": "x.com"}])
    lid = next(iter(fake.leads))
    assert client.post(f"/leads/{lid}/research").status_code == 404


def test_discover_maps_provider_failures_to_502(client, monkeypatch, fake):
    cid = mk(client, monkeypatch)["campaign"]["id"]
    def no_key(*a, **k):
        raise SearchError("TAVILY_API_KEY is not set on the server.")
    monkeypatch.setattr(discovery, "find_candidates", no_key)
    r = client.post(f"/campaigns/{cid}/discover")
    assert r.status_code == 502 and "TAVILY" in r.json()["detail"]


def test_seed_adds_eight_demo_leads_once(client, monkeypatch, fake):
    cid = mk(client, monkeypatch)["campaign"]["id"]
    assert client.post(f"/campaigns/{cid}/seed").json() == {"added": 8}
    assert client.post(f"/campaigns/{cid}/seed").json() == {"added": 0}   # idempotent
    assert all(l["source"] == "seed" and l["website_text"] for l in fake.leads.values())


def test_csv_import_maps_headers_and_skips_bad_rows(client, monkeypatch, fake):
    cid = mk(client, monkeypatch)["campaign"]["id"]
    csv_text = (
        "Company,Website,Contact Name,Job Title,Email\n"
        "Acme Freight,https://www.acme-freight.com/about,Ada Obi,COO,ada@acme-freight.com\n"
        ",nocompany.com,,,\n"
        "Bad Domain Ltd,not a domain,,,\n"
        "NoEmail Inc,noemail.com,,CEO,not-an-email\n"
        "Acme Duplicate,acme-freight.com,,,\n"
    )
    out = client.post(f"/campaigns/{cid}/leads/import", json={"csv": csv_text}).json()
    assert out == {"added": 2, "skipped": 3}
    rows = {l["domain"]: l for l in fake.leads.values()}
    assert rows["acme-freight.com"]["contact_role"] == "COO" and rows["acme-freight.com"]["contact_email"] == "ada@acme-freight.com"
    assert rows["noemail.com"]["contact_email"] is None and all(r["source"] == "csv" for r in rows.values())


def test_csv_without_a_header_row_is_rejected(client, monkeypatch, fake):
    cid = mk(client, monkeypatch)["campaign"]["id"]
    assert client.post(f"/campaigns/{cid}/leads/import", json={"csv": "\n"}).status_code == 422


def test_research_campaign_queues_and_processes_new_and_failed_leads(client, monkeypatch, fake):
    cid = mk(client, monkeypatch)["campaign"]["id"]
    client.post(f"/campaigns/{cid}/seed")
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: ResearchOut(summary="s", fit_score=70, fit_reason="r"))
    leads = list(fake.leads.values())
    leads[0]["status"] = "researched"        # skipped
    leads[1]["status"] = "failed"            # retried
    leads[2]["status"] = "researching"       # stuck: only picked up with force
    assert client.post(f"/campaigns/{cid}/research").json() == {"queued": 6}
    statuses = [l["status"] for l in fake.leads.values()]
    assert statuses.count("researched") == 7 and statuses.count("researching") == 1
    assert client.post(f"/campaigns/{cid}/research?force=true").json() == {"queued": 1}
    assert {l["status"] for l in fake.leads.values()} == {"researched"}
    assert client.post(f"/campaigns/{cid}/research").json() == {"queued": 0}


def test_research_one_lead_returns_the_updated_lead(client, monkeypatch, fake):
    cid = mk(client, monkeypatch)["campaign"]["id"]
    client.post(f"/campaigns/{cid}/seed")
    lid = next(iter(fake.leads))
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: ResearchOut(summary="s", fit_score=55, fit_reason="r", personalization_hook=None))
    lead = client.post(f"/leads/{lid}/research").json()["lead"]
    assert lead["status"] == "researched" and lead["fit_score"] == 55 and lead["personalization_hook"] is None
