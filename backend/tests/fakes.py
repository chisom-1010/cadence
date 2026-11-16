import itertools
import uuid

from app import repo

LEAD_COLUMNS = ["domain", "contact_name", "contact_role", "contact_email", "website_text", "research_summary",
                "fit_score", "fit_reason", "personalization_hook", "error"]


class FakeRepo:
    """In-memory stand-in for app.repo with the same ownership rules."""

    def __init__(self):
        self.campaigns: dict[str, dict] = {}
        self.leads: dict[str, dict] = {}
        self.emails: dict[str, dict] = {}
        self.replies: dict[str, dict] = {}
        self.contacts: dict[str, dict] = {}
        self._n = itertools.count(1)

    def install(self, monkeypatch):
        for name in ["create_campaign", "get_campaign", "update_campaign", "get_lead", "list_leads",
                     "existing_domains", "insert_leads", "claim_lead", "update_lead",
                     "get_email", "get_latest_email", "list_emails", "insert_email", "transition_email",
                     "get_reply", "insert_reply", "update_reply",
                     "list_contacts", "get_contact", "lead_ids_with_contacts", "replace_contacts", "set_primary_contact"]:
            monkeypatch.setattr(repo, name, getattr(self, name))

    def create_campaign(self, user_id, fields):
        row = {"id": str(uuid.uuid4()), "user_id": user_id, "icp": None, "product_pitch": "", "icp_description": "", **fields}
        self.campaigns[row["id"]] = row
        return dict(row)

    def get_campaign(self, user_id, cid):
        c = self.campaigns.get(cid)
        return dict(c) if c and c["user_id"] == user_id else None

    def update_campaign(self, user_id, cid, fields):
        c = self.campaigns.get(cid)
        if not c or c["user_id"] != user_id:
            return None
        c.update(fields)
        return dict(c)

    def get_lead(self, user_id, lid):
        l = self.leads.get(lid)
        return dict(l) if l and l["user_id"] == user_id else None

    def list_leads(self, user_id, campaign_id, statuses=None):
        rows = [l for l in self.leads.values() if l["user_id"] == user_id and l["campaign_id"] == campaign_id]
        if statuses:
            rows = [l for l in rows if l["status"] in statuses]
        return sorted((dict(r) for r in rows), key=lambda r: r["n"])

    def existing_domains(self, user_id, campaign_id):
        return {l["domain"] for l in self.leads.values() if l["user_id"] == user_id and l["campaign_id"] == campaign_id and l["domain"]}

    def insert_leads(self, user_id, campaign_id, rows):
        added = 0
        known = self.existing_domains(user_id, campaign_id)
        for r in rows:
            if r.get("domain") and r["domain"] in known:
                continue
            if r.get("domain"):
                known.add(r["domain"])
            row = {c: None for c in LEAD_COLUMNS}
            row.update(r)
            row.update({"id": str(uuid.uuid4()), "user_id": user_id, "campaign_id": campaign_id, "status": "new", "n": next(self._n)})
            self.leads[row["id"]] = row
            added += 1
        return added

    def claim_lead(self, user_id, lid, from_statuses):
        l = self.leads.get(lid)
        if not l or l["user_id"] != user_id or l["status"] not in from_statuses:
            return None
        l["status"], l["error"] = "researching", None
        return dict(l)

    def update_lead(self, user_id, lid, fields):
        l = self.leads.get(lid)
        if not l or l["user_id"] != user_id:
            return None
        l.update(fields)
        return dict(l)

    # ----- emails -----
    def get_email(self, user_id, eid):
        e = self.emails.get(eid)
        return dict(e) if e and e["user_id"] == user_id else None

    def get_latest_email(self, user_id, lead_id):
        rows = [e for e in self.emails.values() if e["user_id"] == user_id and e["lead_id"] == lead_id]
        return dict(max(rows, key=lambda r: r["n"])) if rows else None

    def list_emails(self, user_id, statuses=None, campaign_id=None):
        rows = [e for e in self.emails.values() if e["user_id"] == user_id]
        if statuses:
            rows = [e for e in rows if e["status"] in statuses]
        if campaign_id:
            rows = [e for e in rows if e["campaign_id"] == campaign_id]
        return sorted((dict(r) for r in rows), key=lambda r: r["n"])

    def insert_email(self, user_id, fields):
        row = {"id": str(uuid.uuid4()), "user_id": user_id, "n": next(self._n), "sent_to": None, "error": None, **fields}
        self.emails[row["id"]] = row
        return dict(row)

    def transition_email(self, user_id, eid, from_statuses, fields):
        e = self.emails.get(eid)
        if not e or e["user_id"] != user_id or e["status"] not in from_statuses:
            return None
        e.update(fields)
        return dict(e)

    # ----- replies -----
    def get_reply(self, user_id, rid):
        r = self.replies.get(rid)
        return dict(r) if r and r["user_id"] == user_id else None

    def insert_reply(self, user_id, fields):
        row = {"id": str(uuid.uuid4()), "user_id": user_id, "label": None, "is_hot": False, "reason": None, **fields}
        self.replies[row["id"]] = row
        return dict(row)

    def update_reply(self, user_id, rid, fields):
        r = self.replies.get(rid)
        if not r or r["user_id"] != user_id:
            return None
        r.update(fields)
        return dict(r)

    # ----- contacts -----
    def list_contacts(self, user_id, lead_id):
        return [dict(c) for c in self.contacts.values() if c["user_id"] == user_id and c["lead_id"] == lead_id]

    def get_contact(self, user_id, cid):
        c = self.contacts.get(cid)
        return dict(c) if c and c["user_id"] == user_id else None

    def lead_ids_with_contacts(self, user_id, campaign_id):
        return {c["lead_id"] for c in self.contacts.values() if c["user_id"] == user_id and c["campaign_id"] == campaign_id}

    def replace_contacts(self, user_id, lead, rows):
        for cid in [k for k, c in self.contacts.items() if c["lead_id"] == lead["id"] and c["user_id"] == user_id]:
            del self.contacts[cid]
        out = []
        for r in rows:
            row = {"id": str(uuid.uuid4()), "user_id": user_id, "lead_id": lead["id"], "campaign_id": lead["campaign_id"], **r}
            self.contacts[row["id"]] = row
            out.append(dict(row))
        return out

    def set_primary_contact(self, user_id, lead_id, cid):
        for c in self.contacts.values():
            if c["lead_id"] == lead_id and c["user_id"] == user_id:
                c["is_primary"] = c["id"] == cid
