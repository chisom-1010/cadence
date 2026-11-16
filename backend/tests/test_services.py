from types import SimpleNamespace

from app.llm import LLMError, LLMRateLimited
from app.schemas import CandidatesOut, Candidate, ICP, QueriesOut, ResearchOut
from app.search import SearchResult
from app.services import discovery, research

ICP_DICT = ICP(summary="Small logistics firms in West Africa", industries=["logistics"], regions=["Togo"]).model_dump()
CAMPAIGN = {"id": "c1", "user_id": "u1", "product_pitch": "Route planning software", "icp": ICP_DICT}


# ---------- discovery ----------
def _llm(candidates):
    def fake(system, user, schema, **kw):
        return QueriesOut(queries=["q1", "q2", "q3"]) if schema is QueriesOut else CandidatesOut(companies=candidates)
    return fake


RESULTS = [
    SearchResult(title="Acme Freight", url="https://www.acme-freight.com/about", content="Road freight in Lome."),
    SearchResult(title="Top 10 logistics firms", url="https://clutch.co/logistics", content="Directory. Zed Cargo (zedcargo.tg) is listed."),
]


def test_discovery_drops_hallucinated_blocked_and_duplicate_domains(monkeypatch, fake):
    cands = [
        Candidate(company_name="Acme Freight", domain="https://www.acme-freight.com/"),
        Candidate(company_name="Acme Freight again", domain="acme-freight.com"),       # duplicate
        Candidate(company_name="Ghost Corp", domain="ghost-corp.com"),                 # not in the results
        Candidate(company_name="LinkedIn page", domain="linkedin.com"),                # blocked
        Candidate(company_name="Zed Cargo", domain="zedcargo.tg", contact_role="COO"),  # appears in snippet text
        Candidate(company_name="Broken", domain="not a domain"),
    ]
    monkeypatch.setattr(discovery, "complete_json", _llm(cands))
    monkeypatch.setattr(discovery, "web_search", lambda q, max_results=8: RESULTS)
    rows, read = discovery.find_candidates(ICP.model_validate(ICP_DICT), "pitch", 20)
    assert [r["domain"] for r in rows] == ["acme-freight.com", "zedcargo.tg"]
    assert rows[1]["contact_role"] == "COO" and all(r["source"] == "search" for r in rows)
    assert read == 2  # the same two URLs came back for each of the three queries, counted once


def test_discover_skips_known_domains_and_reports_counts(monkeypatch, fake):
    c = fake.create_campaign("u1", {"name": "x"})
    campaign = {**CAMPAIGN, "id": c["id"]}
    fake.insert_leads("u1", c["id"], [{"company_name": "Acme", "domain": "acme-freight.com"}])
    cands = [Candidate(company_name="Acme", domain="acme-freight.com"), Candidate(company_name="Zed", domain="zedcargo.tg")]
    monkeypatch.setattr(discovery, "complete_json", _llm(cands))
    monkeypatch.setattr(discovery, "web_search", lambda q, max_results=8: RESULTS)
    out = discovery.discover("u1", campaign)
    assert out == {"results_read": 2, "candidates": 2, "added": 1, "already_known": 1}


def test_discover_respects_the_per_run_limit(monkeypatch, fake):
    monkeypatch.setattr(discovery.settings, "max_leads_per_discovery", 2)
    c = fake.create_campaign("u1", {"name": "x"})
    many = [SearchResult(title=f"T{i}", url=f"https://site{i}.com", content="") for i in range(6)]
    cands = [Candidate(company_name=f"C{i}", domain=f"site{i}.com") for i in range(6)]
    monkeypatch.setattr(discovery, "complete_json", _llm(cands))
    monkeypatch.setattr(discovery, "web_search", lambda q, max_results=8: many)
    assert discovery.discover("u1", {**CAMPAIGN, "id": c["id"]})["added"] == 2


def test_discover_with_no_search_results_adds_nothing(monkeypatch, fake):
    monkeypatch.setattr(discovery, "complete_json", _llm([]))
    monkeypatch.setattr(discovery, "web_search", lambda q, max_results=8: [])
    c = fake.create_campaign("u1", {"name": "x"})
    assert discovery.discover("u1", {**CAMPAIGN, "id": c["id"]})["added"] == 0


# ---------- research ----------
def _lead(fake, **over):
    c = fake.create_campaign("u1", {"name": "x"})
    fake.insert_leads("u1", c["id"], [{"company_name": "Acme", "domain": "acme-freight.com", **over}])
    lead = next(iter(fake.leads.values()))
    return {**CAMPAIGN, "id": c["id"]}, dict(lead)


GOOD = ResearchOut(summary="Road freight.", fit_score=82, fit_reason="Matches the region.", personalization_hook="Opened a Lome hub")
LONG = "Acme Freight moves pallets across the region. " * 20


def test_research_success_fills_fields_and_sets_researched(monkeypatch, fake):
    campaign, lead = _lead(fake)
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: LONG)
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: GOOD)
    out = research.research_lead("u1", campaign, lead)
    assert out["status"] == "researched" and out["fit_score"] == 82
    assert out["research_summary"] == "Road freight." and out["personalization_hook"] == "Opened a Lome hub"
    assert out["error"] is None and out["website_text"].startswith("Acme Freight")


def test_research_without_readable_site_is_no_data_and_never_calls_the_llm(monkeypatch, fake):
    campaign, lead = _lead(fake)
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: None)
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("LLM must not be called")))
    assert research.research_lead("u1", campaign, lead)["status"] == "no_data"
    campaign, lead = _lead(fake, domain="tiny.com")
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: "too short")
    assert research.research_lead("u1", campaign, lead)["status"] == "no_data"


def test_research_records_llm_failures_on_the_lead(monkeypatch, fake):
    campaign, lead = _lead(fake)
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: LONG)
    def boom(*a, **k):
        raise LLMRateLimited("rate limited")
    monkeypatch.setattr(research, "complete_json", boom)
    out = research.research_lead("u1", campaign, lead)
    assert out["status"] == "failed" and "rate limited" in out["error"]
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: (_ for _ in ()).throw(LLMError("bad json")))
    campaign, lead = _lead(fake, domain="b.com")
    assert research.research_lead("u1", campaign, lead)["status"] == "failed"


def test_seeded_text_is_used_without_fetching(monkeypatch, fake):
    campaign, lead = _lead(fake, domain="demo.example", website_text=LONG)
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: (_ for _ in ()).throw(AssertionError("must not fetch")))
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: GOOD)
    assert research.research_lead("u1", campaign, lead)["status"] == "researched"


def test_research_uses_the_fast_model_when_configured(monkeypatch, fake):
    campaign, lead = _lead(fake)
    seen = {}
    monkeypatch.setattr(research.settings, "llm_model_fast", "small-model")
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: LONG)
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: seen.update(k) or GOOD)
    research.research_lead("u1", campaign, lead)
    assert seen["model"] == "small-model"


def test_research_many_skips_leads_already_handled_and_survives_errors(monkeypatch, fake):
    c = fake.create_campaign("u1", {"name": "x"})
    fake.insert_leads("u1", c["id"], [{"company_name": n, "domain": f"{n}.com"} for n in ["a", "b", "c"]])
    a, b, cc = [l for l in fake.list_leads("u1", c["id"])]
    fake.update_lead("u1", a["id"], {"status": "researched"})            # already done: must be skipped
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: LONG)
    def llm(*args, **kw):
        if "b.com" in args[1]:
            raise RuntimeError("unexpected")
        return GOOD
    monkeypatch.setattr(research, "complete_json", llm)
    research.research_many("u1", {**CAMPAIGN, "id": c["id"]}, [a["id"], b["id"], cc["id"]])
    status = {l["company_name"]: l["status"] for l in fake.list_leads("u1", c["id"])}
    assert status == {"a": "researched", "b": "failed", "c": "researched"}
    assert fake.leads[b["id"]]["error"].startswith("Unexpected error")


def test_nobody_can_research_another_users_lead(monkeypatch, fake):
    campaign, lead = _lead(fake)
    monkeypatch.setattr(research, "fetch_site_text", lambda d, n: LONG)
    monkeypatch.setattr(research, "complete_json", lambda *a, **k: GOOD)
    out = research.research_lead("intruder", campaign, lead)
    assert out == lead and fake.leads[lead["id"]]["status"] == "new"
