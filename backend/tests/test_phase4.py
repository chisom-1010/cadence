from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.auth import current_user
from app.dnscheck import has_mx
from app.llm import LLMError
from app.main import app
from app.schemas import CandidatesOut, Candidate, CompetitorOut, CompetitorsOut, ICP, PeopleOut, PersonOut, QueriesOut
from app.search import SearchResult
from app.services import competitors, discovery, people

PAGE = "Our team. Jane Doe, Head of Operations. John Smith, Chief Executive Officer. Contact: info@acme.example, jane.doe@acme.example"
ICP_ = ICP(summary="s", target_roles=["Operations Manager", "Head of Operations"])


@pytest.fixture
def client(fake):
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u1", email="a@b.co")
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def setup(fake, monkeypatch):
    monkeypatch.setattr(people.settings, "research_delay_seconds", 0)
    c = fake.create_campaign("u1", {"name": "T", "product_pitch": "Route planning", "icp": ICP_.model_dump()})
    fake.insert_leads("u1", c["id"], [{"company_name": "Acme", "domain": "acme.example", "source": "search"}])
    lid = next(iter(fake.leads))
    fake.update_lead("u1", lid, {"status": "researched", "fit_score": 80})
    return SimpleNamespace(cid=c["id"], lid=lid)


def llm_people(*names):
    return lambda *a, **k: PeopleOut(people=[PersonOut(name=n, role=r) for n, r in names])


def site(monkeypatch, text=PAGE, emails=("info@acme.example", "jane.doe@acme.example")):
    monkeypatch.setattr(people, "gather", lambda domain: (text, set(emails)) if text else ("", set()))


# ---------- extraction guards ----------
def test_names_not_on_the_pages_are_dropped(monkeypatch):
    monkeypatch.setattr(people, "complete_json", llm_people(("Jane Doe", "Head of Operations"), ("Elon Musk", "CEO"), ("Prince", ""), ("Bob 2 Smith", "")))
    out = people.extract_people(PAGE)
    assert [p["full_name"] for p in out] == ["Jane Doe"]


def test_a_title_that_is_not_on_the_pages_is_removed_but_the_person_stays(monkeypatch):
    monkeypatch.setattr(people, "complete_json", llm_people(("John Smith", "Chief Revenue Wizard")))
    assert people.extract_people(PAGE) == [{"full_name": "John Smith", "role": ""}]


def test_email_matching_uses_published_addresses_only_for_that_person():
    emails = {"info@acme.example", "jane.doe@acme.example", "jsmith@acme.example", "random@acme.example"}
    assert people._match_email("Jane Doe", emails) == "jane.doe@acme.example"
    assert people._match_email("John Smith", emails) == "jsmith@acme.example"
    assert people._match_email("Mary Jones", emails) is None
    assert people._match_email("Ana Info", {"info@acme.example"}) is None   # generic inboxes never belong to a person


def test_guess_depends_on_whether_the_domain_accepts_mail(monkeypatch):
    for mx, expected in [(True, ("mary.jones@acme.example", "guessed")), (False, (None, "no_mail_server")), (None, ("mary.jones@acme.example", "unknown"))]:
        monkeypatch.setattr(people, "has_mx", lambda d, mx=mx: mx)
        assert people._guess("Mary Jones", "acme.example") == expected
    assert people._guess("Cher", "acme.example") == (None, "unknown")           # one name: nothing sensible to guess
    monkeypatch.setattr(people, "has_mx", lambda d: True)
    assert people._guess("Zoë Müller", "acme.example")[0] == "zoe.muller@acme.example"


def test_role_scoring_prefers_target_roles_then_seniority():
    t = ["Operations Manager"]
    assert people.role_score("Head of Operations", t) > people.role_score("Chief Executive Officer", t) > people.role_score("Intern", t)


# ---------- find_people ----------
def test_find_people_stores_ranks_and_fills_the_lead(monkeypatch, fake, setup):
    monkeypatch.setattr(people, "complete_json", llm_people(("John Smith", "Chief Executive Officer"), ("Jane Doe", "Head of Operations")))
    monkeypatch.setattr(people, "has_mx", lambda d: True)
    site(monkeypatch)
    lead = fake.get_lead("u1", setup.lid)
    stored = people.find_people("u1", fake.get_campaign("u1", setup.cid), lead)
    by = {c["full_name"]: c for c in stored}
    assert by["Jane Doe"]["email_status"] == "found" and by["Jane Doe"]["is_primary"]       # target role wins, published address
    assert by["John Smith"]["email_status"] == "guessed" and by["John Smith"]["email"] == "john.smith@acme.example"
    assert by["General inbox"]["email_status"] == "role_address" and not by["General inbox"]["is_primary"]
    l = fake.get_lead("u1", setup.lid)
    assert (l["contact_name"], l["contact_email"]) == ("Jane Doe", "jane.doe@acme.example")


def test_a_supplied_csv_contact_is_never_overwritten(monkeypatch, fake, setup):
    fake.update_lead("u1", setup.lid, {"contact_name": "Pat Lee", "contact_email": "pat@acme.example"})
    monkeypatch.setattr(people, "complete_json", llm_people(("Jane Doe", "Head of Operations")))
    site(monkeypatch)
    people.find_people("u1", fake.get_campaign("u1", setup.cid), fake.get_lead("u1", setup.lid))
    assert fake.get_lead("u1", setup.lid)["contact_email"] == "pat@acme.example"


def test_unreadable_website_is_a_clear_error(monkeypatch, fake, setup, client):
    site(monkeypatch, text="")
    r = client.post(f"/leads/{setup.lid}/people")
    assert r.status_code == 422 and "could not be read" in r.json()["detail"]


def test_llm_failure_maps_to_502_and_bulk_records_it_on_the_lead(monkeypatch, fake, setup, client):
    site(monkeypatch)
    monkeypatch.setattr(people, "complete_json", lambda *a, **k: (_ for _ in ()).throw(LLMError("down")))
    assert client.post(f"/leads/{setup.lid}/people").status_code == 502
    assert client.post(f"/campaigns/{setup.cid}/people").json() == {"queued": 1}
    assert "People search failed" in fake.get_lead("u1", setup.lid)["error"]


def test_seed_leads_get_offline_people_with_mixed_email_states(fake, client):
    c = fake.create_campaign("u1", {"name": "T", "icp": ICP_.model_dump()})
    client.post(f"/campaigns/{c['id']}/seed")
    lid = next(l["id"] for l in fake.leads.values() if l["domain"] == "stonebridge-supplies.example")
    out = client.post(f"/leads/{lid}/people").json()
    states = {c["email_status"] for c in out["contacts"]}
    assert {"found", "guessed", "role_address"} <= states and all(c["source"] == "seed" for c in out["contacts"])
    assert sum(c["is_primary"] for c in out["contacts"]) == 1


def test_bulk_only_queues_good_fit_leads_without_people(monkeypatch, fake, setup, client):
    site(monkeypatch)
    monkeypatch.setattr(people, "complete_json", llm_people(("Jane Doe", "Head of Operations")))
    monkeypatch.setattr(people, "has_mx", lambda d: True)
    assert client.post(f"/campaigns/{setup.cid}/people").json() == {"queued": 1}
    assert client.post(f"/campaigns/{setup.cid}/people").json() == {"queued": 0}      # already done


# ---------- use contact ----------
def test_use_contact_switches_the_person_and_flags_a_stale_draft(monkeypatch, fake, setup, client):
    monkeypatch.setattr(people, "complete_json", llm_people(("John Smith", "Chief Executive Officer"), ("Jane Doe", "Head of Operations")))
    monkeypatch.setattr(people, "has_mx", lambda d: True)
    site(monkeypatch)
    contacts = client.post(f"/leads/{setup.lid}/people").json()["contacts"]
    john = next(c for c in contacts if c["full_name"] == "John Smith")
    out = client.post(f"/leads/{setup.lid}/contacts/{john['id']}/use").json()
    assert out["lead"]["contact_email"] == "john.smith@acme.example" and out["draft_outdated"] is False
    assert next(c for c in fake.contacts.values() if c["id"] == john["id"])["is_primary"]
    fake.insert_email("u1", {"lead_id": setup.lid, "campaign_id": setup.cid, "subject": "s", "body": "b", "status": "draft"})
    assert client.post(f"/leads/{setup.lid}/contacts/{john['id']}/use").json()["draft_outdated"] is True


def test_use_contact_is_blocked_after_approval_or_without_an_address(monkeypatch, fake, setup, client):
    row = fake.replace_contacts("u1", fake.get_lead("u1", setup.lid), [
        {"full_name": "No Mail", "role": "", "email": None, "email_status": "no_mail_server", "source": "website", "is_primary": False},
        {"full_name": "Has Mail", "role": "", "email": "has@acme.example", "email_status": "found", "source": "website", "is_primary": False}])
    assert client.post(f"/leads/{setup.lid}/contacts/{row[0]['id']}/use").status_code == 409
    fake.insert_email("u1", {"lead_id": setup.lid, "campaign_id": setup.cid, "subject": "s", "body": "b", "status": "approved"})
    assert client.post(f"/leads/{setup.lid}/contacts/{row[1]['id']}/use").status_code == 409


def test_other_users_cannot_use_find_or_switch_people(fake, setup, client):
    row = fake.replace_contacts("u1", fake.get_lead("u1", setup.lid), [{"full_name": "A B", "email": "a@acme.example", "email_status": "found", "source": "website", "is_primary": False}])
    app.dependency_overrides[current_user] = lambda: SimpleNamespace(id="u2", email="x@y.co")
    assert client.post(f"/leads/{setup.lid}/people").status_code == 404
    assert client.post(f"/campaigns/{setup.cid}/people").status_code == 404
    assert client.post(f"/campaigns/{setup.cid}/competitors").status_code == 404
    assert client.post(f"/leads/{setup.lid}/contacts/{row[0]['id']}/use").status_code == 404


def test_new_endpoints_require_a_token(fake):
    app.dependency_overrides.clear()
    c = TestClient(app)
    for path in ["/leads/x/people", "/campaigns/x/people", "/leads/x/contacts/y/use", "/campaigns/x/competitors"]:
        assert c.post(path).status_code == 401, path


# ---------- mx lookup ----------
class R:
    def __init__(self, data): self._d = data
    def raise_for_status(self): pass
    def json(self): return self._d


@pytest.mark.parametrize("data,expected", [
    ({"Status": 0, "Answer": [{"type": 15, "data": "10 mail.acme.example."}]}, True),
    ({"Status": 0, "Answer": [{"type": 15, "data": "0 ."}]}, False),       # null MX
    ({"Status": 3}, False),
    ({"Status": 0}, False),
    ({"Status": 2}, None),
])
def test_has_mx(monkeypatch, data, expected):
    has_mx.cache_clear()
    monkeypatch.setattr("app.dnscheck.httpx.get", lambda *a, **k: R(data))
    assert has_mx("x.example") is expected


def test_has_mx_returns_none_on_network_failure(monkeypatch):
    import httpx
    has_mx.cache_clear()
    monkeypatch.setattr("app.dnscheck.httpx.get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("no")))
    assert has_mx("y.example") is None


# ---------- competitors ----------
RES = [SearchResult(title="Best route planners", url="https://routeco.example/", content="RouteCo plans fleet routes. Also see fleetly.example and g2.com listing."),
       SearchResult(title="G2", url="https://g2.com/x", content="reviews")]


def comp_llm(rows):
    return lambda s, u, schema, **k: QueriesOut(queries=["q1", "q2"]) if schema is QueriesOut else CompetitorsOut(competitors=rows)


def test_competitors_must_appear_in_results_and_not_be_directories(monkeypatch):
    rows = [CompetitorOut(name="RouteCo", domain="https://www.routeco.example", note="Fleet routing"),
            CompetitorOut(name="Fleetly", domain="fleetly.example"),
            CompetitorOut(name="Ghost", domain="ghost.example"),
            CompetitorOut(name="G2", domain="g2.com"),
            CompetitorOut(name="Dup", domain="routeco.example")]
    monkeypatch.setattr(competitors, "complete_json", comp_llm(rows))
    monkeypatch.setattr(competitors, "web_search", lambda q, max_results=8: RES)
    assert [c["domain"] for c in competitors.find_competitors("Route planning")] == ["routeco.example", "fleetly.example"]


def test_competitors_endpoint_saves_them_and_needs_a_pitch(monkeypatch, fake, setup, client):
    monkeypatch.setattr(competitors, "complete_json", comp_llm([CompetitorOut(name="RouteCo", domain="routeco.example")]))
    monkeypatch.setattr(competitors, "web_search", lambda q, max_results=8: RES)
    assert client.post(f"/campaigns/{setup.cid}/competitors").json()["competitors"][0]["domain"] == "routeco.example"
    assert fake.get_campaign("u1", setup.cid)["competitors"][0]["name"] == "RouteCo"
    empty = fake.create_campaign("u1", {"name": "E", "product_pitch": "  "})
    assert client.post(f"/campaigns/{empty['id']}/competitors").status_code == 409


def test_discovery_never_adds_a_known_competitor(monkeypatch, fake):
    c = fake.create_campaign("u1", {"name": "x"})
    campaign = {"id": c["id"], "product_pitch": "p", "icp": ICP_.model_dump(), "competitors": [{"name": "RouteCo", "domain": "routeco.example"}]}
    res = [SearchResult(title="A", url="https://routeco.example", content=""), SearchResult(title="B", url="https://client.example", content="")]
    cands = CandidatesOut(companies=[Candidate(company_name="RouteCo", domain="routeco.example"), Candidate(company_name="Client", domain="client.example")])
    monkeypatch.setattr(discovery, "complete_json", lambda s, u, schema, **k: QueriesOut(queries=["a"]) if schema is QueriesOut else cands)
    monkeypatch.setattr(discovery, "web_search", lambda q, max_results=8: res)
    out = discovery.discover("u1", campaign)
    assert out["added"] == 1 and [l["domain"] for l in fake.leads.values()] == ["client.example"]
