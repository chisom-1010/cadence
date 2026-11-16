"""Safe website fetching. Domains come from search results or CSV files, so never trust them:
block private and internal addresses (SSRF), cap the size, and only read HTML."""
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

MAX_BYTES = 600_000
UA = "Mozilla/5.0 (compatible; OutreachResearchBot/1.0)"
_DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")


def clean_domain(value: str | None) -> str | None:
    """'https://www.Acme.com/about' -> 'acme.com'. Returns None if it isn't a plausible domain."""
    if not value:
        return None
    v = value.strip().lower()
    v = re.sub(r"^[a-z]+://", "", v)
    v = v.split("/")[0].split("?")[0].split("#")[0].split("@")[-1].split(":")[0]
    v = re.sub(r"^www\.", "", v)
    return v if _DOMAIN_RE.match(v) else None


def is_public_host(host: str) -> bool:
    """True only if every address the host resolves to is a public internet address."""
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    for info in infos:
        try:
            if not ipaddress.ip_address(info[4][0]).is_global:
                return False
        except ValueError:
            return False
    return True


def _allowed(url: str) -> bool:
    u = urlparse(url)
    return u.scheme in ("http", "https") and bool(u.hostname) and u.port in (None, 80, 443) and is_public_host(u.hostname)


def fetch_html(url: str, max_hops: int = 3) -> str | None:
    for _ in range(max_hops + 1):
        if not _allowed(url):
            return None
        try:
            with httpx.stream("GET", url, headers={"User-Agent": UA}, timeout=10, follow_redirects=False) as r:
                if r.is_redirect:
                    url = urljoin(url, r.headers.get("location", ""))
                    continue
                if r.status_code >= 400 or "html" not in r.headers.get("content-type", "text/html"):
                    return None
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > MAX_BYTES:
                        break
                return bytes(buf).decode(r.encoding or "utf-8", errors="replace")
        except httpx.HTTPError:
            return None
    return None


def html_to_text(html: str, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    desc = (meta.get("content") or "").strip() if meta else ""
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "form", "iframe"]):
        tag.decompose()
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    parts = [p for p in (f"Title: {title}" if title else "", f"Description: {desc}" if desc else "", body) if p]
    return "\n".join(parts)[:max_chars]


def fetch_site_text(domain: str, max_chars: int) -> str | None:
    html = fetch_html(f"https://{domain}")
    if html is None:
        html = fetch_html(f"http://{domain}")
    return html_to_text(html, max_chars) if html else None
