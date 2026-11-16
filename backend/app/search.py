"""Web search for lead discovery (Tavily). Swap providers by editing only this file."""
import httpx
from pydantic import BaseModel

from app.config import settings


class SearchError(RuntimeError):
    pass


class SearchResult(BaseModel):
    title: str = ""
    url: str
    content: str = ""


def web_search(query: str, max_results: int = 8) -> list[SearchResult]:
    if not settings.tavily_api_key:
        raise SearchError("TAVILY_API_KEY is not set on the server.")
    try:
        r = httpx.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
            json={"query": query, "max_results": max_results, "search_depth": "basic"},
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise SearchError(f"Could not reach the search provider: {exc}") from exc
    if r.status_code >= 400:
        raise SearchError(f"Search provider returned {r.status_code}: {r.text[:200]}")
    try:
        items = r.json().get("results", [])
    except ValueError as exc:
        raise SearchError("Unexpected response from the search provider.") from exc
    return [
        SearchResult(title=i.get("title") or "", url=i["url"], content=i.get("content") or "")
        for i in items
        if i.get("url")
    ]
