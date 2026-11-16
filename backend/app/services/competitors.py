"""Find competitors of what the user sells. Same rule as lead discovery: names and domains are
taken only from real search results, and every domain is checked against them."""
from app import repo
from app.llm import complete_json
from app.net import clean_domain
from app.schemas import CompetitorsOut, QueriesOut
from app.search import SearchResult, web_search
from app.services.discovery import _is_blocked, _results_blob

QUERY_SYSTEM = """You write web search queries that find competitors of a product.
Write exactly 2 different queries, each under 10 words, such as "<product type> software alternatives" or "best <product type> tools".
Do not include quotation marks or the user's own brand name."""

EXTRACT_SYSTEM = """You list competing products or companies from web search results.
Rules:
- List only companies named in the results below. Never add one from your own memory.
- Each needs its own website domain, and that domain must appear in the results text. If it does not, skip it.
- Skip directories, review sites, news sites and social networks. Skip the user's own company.
- note: at most 15 words on what they sell, using only the results.
- Return at most 8."""


def find_competitors(pitch: str) -> list[dict]:
    queries = complete_json(QUERY_SYSTEM, f"What the user sells: {pitch}", QueriesOut, temperature=0.3).queries[:2]
    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    for q in queries:
        for r in web_search(q, max_results=8):
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                results.append(r)
    results = results[:16]
    if not results:
        return []
    listing = "\n\n".join(f"[{i + 1}] {r.title}\nURL: {r.url}\n{r.content[:400]}" for i, r in enumerate(results))
    out = complete_json(EXTRACT_SYSTEM, f"What the user sells: {pitch}\n\nSearch results:\n{listing}", CompetitorsOut, temperature=0.1, max_tokens=1500)
    blob = _results_blob(results)
    rows, seen = [], set()
    for c in out.competitors:
        domain = clean_domain(c.domain)
        if not domain or domain in seen or _is_blocked(domain) or domain not in blob:
            continue
        seen.add(domain)
        rows.append({"name": c.name.strip()[:120], "domain": domain, "note": c.note.strip()[:160]})
    return rows[:8]


def refresh(user_id: str, campaign: dict) -> list[dict]:
    rows = find_competitors(campaign["product_pitch"])
    repo.update_campaign(user_id, campaign["id"], {"competitors": rows})
    return rows
