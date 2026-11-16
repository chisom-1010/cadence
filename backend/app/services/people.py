"""Find the decision makers at a lead's company, and work out how to email them, with free tools only.

Names come from the company's own website pages and must appear there word for word, so the model
cannot invent a person. Emails come from the same pages when they are published. Otherwise we guess
first.last@domain, say so, and check that the domain accepts mail at all. We never claim a guess is verified."""
import re
import time
import unicodedata

from app import repo
from app.config import settings
from app.dnscheck import has_mx
from app.llm import LLMError, complete_json
from app.net import fetch_html, html_to_text
from app.schemas import ICP, PeopleOut
from app.services.seed import SEED_PEOPLE

PATHS = ["", "/about", "/about-us", "/team", "/our-team", "/leadership", "/contact"]
MAX_PAGES = 5
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
GENERIC_LOCALS = {"info", "contact", "hello", "sales", "support", "admin", "office", "enquiries", "inquiries", "mail",
                  "team", "hr", "careers", "help", "service", "contactus", "enquiry", "booking", "reception"}
SENIOR = ("founder", "owner", "ceo", "chief", "director", "head", "president", "managing", "partner", "vp", "vice", "cto", "coo", "cfo", "manager", "lead")
JUNIOR = ("intern", "assistant", "trainee", "junior", "apprentice")
STATUS_RANK = {"found": 3, "guessed": 2, "unknown": 1, "no_mail_server": 0, "role_address": 0}

SYSTEM = """You list the people named on a company's own website pages.
Rules:
- Include a person only if their full name (first and last) appears in the text. Copy the name exactly as written.
- role: the job title written next to that name in the text. Leave it empty if none is written. Never guess a title.
- Skip customers, testimonial authors, quoted outside experts, and people who work at other companies.
- At most 8 people. If no staff are named, return an empty list."""


class PeopleError(RuntimeError):
    pass


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _name_tokens(name: str) -> list[str]:
    name = re.sub(r"\b(dr|mr|mrs|ms|prof|eng)\.?\s", "", _fold(name) + " ", flags=re.I)
    return [t for t in re.findall(r"[a-z]+", name) if len(t) > 1]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _fold(text)).strip()


def gather(domain: str) -> tuple[str, set[str]]:
    """Fetch a few likely pages. Returns (combined text, on-site email addresses for this domain)."""
    texts: list[str] = []
    emails: set[str] = set()
    for i, path in enumerate(PATHS):
        if len(texts) >= MAX_PAGES:
            break
        html = fetch_html(f"https://{domain}{path}")
        if html is None and i == 0:
            html = fetch_html(f"http://{domain}")
        if html is None:
            if i == 0:
                return "", set()  # the site itself is unreachable, so stop early
            continue
        for m in EMAIL_RE.findall(html):
            m = m.lower()
            host = m.split("@")[1]
            if host == domain or host.endswith("." + domain):
                emails.add(m)
        texts.append(f"[page {path or '/'}]\n{html_to_text(html, 3500)}")
    return "\n\n".join(texts), emails


def extract_people(blob: str) -> list[dict]:
    out = complete_json(SYSTEM, f"Website text:\n{blob[:12000]}", PeopleOut,
                        model=settings.llm_model_fast or settings.llm_model or None, temperature=0.0, max_tokens=1500)
    haystack = _norm(blob)
    people, seen = [], set()
    for p in out.people:
        name = " ".join(p.name.split())
        if len(_name_tokens(name)) < 2 or re.search(r"\d", name) or _norm(name) in seen:
            continue
        if _norm(name) not in haystack:  # anti-hallucination guard: the name must really be on the pages
            continue
        seen.add(_norm(name))
        role = " ".join(p.role.split())[:120]
        if role and _norm(role) not in haystack:
            role = ""  # the title was not on the pages either, so drop it
        people.append({"full_name": name[:120], "role": role})
    return people[:8]


def _match_email(name: str, emails: set[str]) -> str | None:
    toks = _name_tokens(name)
    if len(toks) < 2:
        return None
    first, last = toks[0], toks[-1]
    ok = {first, last, first + last, last + first, first[0] + last, first + last[0]}
    for e in sorted(emails):
        local = re.sub(r"[^a-z]", "", e.split("@")[0])
        if e.split("@")[0] not in GENERIC_LOCALS and local in ok:
            return e
    return None


def _guess(name: str, domain: str) -> tuple[str | None, str]:
    """(email, status) for a person whose address is not published."""
    toks = _name_tokens(name)
    if len(toks) < 2:
        return None, "unknown"
    guess = f"{toks[0]}.{toks[-1]}@{domain}"
    mx = has_mx(domain)
    if mx is True:
        return guess, "guessed"
    if mx is False:
        return None, "no_mail_server"
    return guess, "unknown"


def role_score(role: str, target_roles: list[str]) -> int:
    r = _norm(role or "")
    if not r:
        return 0
    score = 0
    words = {w for t in target_roles for w in re.findall(r"[a-z]+", _norm(t)) if len(w) > 3}
    if any(w in r for w in words):
        score += 3
    if any(k in r for k in SENIOR):
        score += 2
    if any(k in r for k in JUNIOR):
        score -= 2
    return score


def _pick_primary(rows: list[dict], target_roles: list[str]) -> int | None:
    best, best_key = None, None
    for i, r in enumerate(rows):
        if r["email_status"] == "role_address":
            key = (-1, 0)
        else:
            key = (role_score(r.get("role") or "", target_roles), STATUS_RANK.get(r["email_status"], 0))
        if best_key is None or key > best_key:
            best, best_key = i, key
    return best


def _rows_from_website(lead: dict) -> list[dict]:
    blob, emails = gather(lead["domain"])
    if not blob:
        raise PeopleError("The website could not be read, so no people could be found.")
    rows = []
    for p in extract_people(blob):
        email = _match_email(p["full_name"], emails)
        if email:
            status = "found"
        else:
            email, status = _guess(p["full_name"], lead["domain"])
        rows.append({**p, "email": email, "email_status": status, "source": "website"})
    generic = sorted(e for e in emails if e.split("@")[0] in GENERIC_LOCALS and e not in {r["email"] for r in rows})
    if generic:
        rows.append({"full_name": "General inbox", "role": "Company address", "email": generic[0], "email_status": "role_address", "source": "website"})
    return rows


def _rows_from_seed(lead: dict) -> list[dict]:
    return [{"full_name": n, "role": r, "email": e, "email_status": s, "source": "seed"} for n, r, e, s in SEED_PEOPLE[lead["domain"]]]


def find_people(user_id: str, campaign: dict, lead: dict) -> list[dict]:
    """Find, store and rank the people for a lead. Returns the stored contacts. Raises PeopleError / LLMError."""
    if not lead.get("domain"):
        raise PeopleError("This lead has no website domain.")
    rows = _rows_from_seed(lead) if lead.get("source") == "seed" and lead["domain"] in SEED_PEOPLE else _rows_from_website(lead)

    icp = ICP.model_validate(campaign["icp"]) if campaign.get("icp") else None
    primary = _pick_primary(rows, icp.target_roles if icp else [])
    for i, r in enumerate(rows):
        r["is_primary"] = i == primary
    stored = repo.replace_contacts(user_id, lead, rows)

    # Fill the lead's own contact fields only when nothing was supplied (a CSV address always wins)
    if primary is not None and not lead.get("contact_email") and stored:
        p = next((c for c in stored if c["is_primary"]), None)
        if p and p.get("email"):
            repo.update_lead(user_id, lead["id"], {"contact_name": None if p["full_name"] == "General inbox" else p["full_name"],
                                                   "contact_role": p.get("role") or None, "contact_email": p["email"]})
    return stored


def find_many(user_id: str, campaign: dict, lead_ids: list[str]) -> None:
    for lead_id in lead_ids:
        try:
            lead = repo.get_lead(user_id, lead_id)
            if lead:
                find_people(user_id, campaign, lead)
        except (PeopleError, LLMError) as exc:
            repo.update_lead(user_id, lead_id, {"error": f"People search failed: {exc}"[:300]})
        except Exception as exc:  # noqa: BLE001
            repo.update_lead(user_id, lead_id, {"error": f"People search failed unexpectedly: {exc}"[:300]})
        time.sleep(settings.research_delay_seconds)


class ContactBlocked(Exception):
    pass


def use_contact(user_id: str, lead: dict, contact: dict) -> dict:
    """Make `contact` the person this lead's email is written to. Returns the updated lead."""
    latest = repo.get_latest_email(user_id, lead["id"])
    if latest and latest["status"] == "approved":
        raise ContactBlocked("This lead's email is already approved. Edit or reject it in the queue first, then change the person.")
    if not contact.get("email"):
        raise ContactBlocked("This person has no usable email address.")
    repo.set_primary_contact(user_id, lead["id"], contact["id"])
    return repo.update_lead(user_id, lead["id"], {
        "contact_name": None if contact["full_name"] == "General inbox" else contact["full_name"],
        "contact_role": contact.get("role") or None, "contact_email": contact["email"]}) or lead
