"""Does a domain accept email at all? Asks Cloudflare's DNS-over-HTTPS service for MX records.
Returns True / False, or None when the lookup itself failed (so callers never claim more than they know)."""
from functools import lru_cache

import httpx


@lru_cache(maxsize=512)
def has_mx(domain: str) -> bool | None:
    try:
        r = httpx.get("https://cloudflare-dns.com/dns-query", params={"name": domain, "type": "MX"},
                      headers={"accept": "application/dns-json"}, timeout=8)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    if data.get("Status") == 3:  # NXDOMAIN
        return False
    answers = [a for a in data.get("Answer", []) if a.get("type") == 15]
    if answers:
        # a "null MX" ("0 .") means the domain explicitly accepts no mail
        return any(str(a.get("data", "")).split()[-1:] not in ([], ["."]) for a in answers)
    return False if data.get("Status") == 0 else None
