"""Lead discovery. The LLM never names companies from memory: it only extracts them from real
search results, and every domain it returns is checked against those results."""
from app import repo
from app.config import settings
from app.llm import complete_json
from app.net import clean_domain
from app.schemas import CandidatesOut, ICP, QueriesOut
from app.search import SearchResult, web_search

# Directories and social sites are not a company's own website
BLOCKED = {
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "tiktok.com",
    "crunchbase.com", "zoominfo.com", "dnb.com", "yelp.com", "glassdoor.com", "indeed.com", "g2.com",
    "capterra.com", "clutch.co", "trustpilot.com", "wikipedia.org", "reddit.com", "medium.com", "quora.com",
    "google.com", "bing.com", "amazon.com", "github.com", "pinterest.com", "forbes.com", "bloomberg.com",
}

QUERY_SYSTEM = """You write web search queries that find the websites of companies matching an ideal customer profile.
Write exactly 3 different queries, each under 12 words, aimed at finding company websites or lists of such companies.
Use the profile's industries, regions and keywords. Do not include quotation marks."""

EXTRACT_SYSTEM = """You extract companies from web search results for sales prospecting.
Rules:
- List only companies that are named in the results below. Never add a company from your own memory.
- Each company needs its own website domain, and that domain must appear in the results text (in a URL or in the text). If it does not, skip the company.
- Skip directories, news sites, social networks and software review sites.
- Prefer companies that match the ideal customer profile. Skip clear mismatches.
- Return at most {limit} companies."""


def _is_blocked(domain: str) -> bool:
    return any(domain == b or domain.endswith("." + b) for b in BLOCKED)


def _results_blob(results: list[SearchResult]) -> str:
    return "\n".join(f"{r.url}\n{r.title}\n{r.content}" for r in results).lower()


def find_candidates(icp: ICP, product_pitch: str, limit: int) -> tuple[list[dict], int]:
    """Returns (candidate lead rows, number of search results read)."""
    icp_json = icp.model_dump_json()
    queries = complete_json(QUERY_SYSTEM, f"Ideal customer profile: {icp_json}\nWhat we sell: {product_pitch or '(not provided)'}", QueriesOut, temperature=0.4).queries[:3]

    results: list[SearchResult] = []
    seen_urls: set[str] = set()
    for q in queries:
        for r in web_search(q, max_results=8):
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                results.append(r)
    results = results[:24]
    if not results:
        return [], 0

    listing = "\n\n".join(f"[{i + 1}] {r.title}\nURL: {r.url}\n{r.content[:400]}" for i, r in enumerate(results))
    out = complete_json(
        EXTRACT_SYSTEM.format(limit=limit),
        f"Ideal customer profile: {icp_json}\n\nSearch results:\n{listing}",
        CandidatesOut,
        temperature=0.1,
        max_tokens=2000,
    )

    blob = _results_blob(results)
    rows, seen = [], set()
    for c in out.companies:
        domain = clean_domain(c.domain)
        if not domain or domain in seen or _is_blocked(domain):
            continue
        if domain not in blob:  # hallucination guard: the domain must appear in the real results
            continue
        seen.add(domain)
        rows.append({"company_name": c.company_name.strip()[:200], "domain": domain, "contact_role": (c.contact_role or None), "source": "search"})
    return rows, len(results)


def discover(user_id: str, campaign: dict) -> dict:
    icp = ICP.model_validate(campaign["icp"])
    limit = settings.max_leads_per_discovery
    rows, read = find_candidates(icp, campaign.get("product_pitch", ""), limit)
    known = repo.existing_domains(user_id, campaign["id"])
    competitors = {c["domain"] for c in (campaign.get("competitors") or []) if c.get("domain")}  # never pitch a competitor
    fresh = [r for r in rows if r["domain"] not in known and r["domain"] not in competitors][:limit]
    added = repo.insert_leads(user_id, campaign["id"], fresh)
    return {"results_read": read, "candidates": len(rows), "added": added, "already_known": len(rows) - len(fresh)}
