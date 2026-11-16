"use client";

import { useCallback, useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { errorText, post } from "../lib/api";
import type { Contact, EmailState, Lead } from "../lib/types";

const STATE_LABEL: Record<EmailState, string> = {
  found: "Published",
  guessed: "Guessed",
  role_address: "Shared inbox",
  no_mail_server: "No mail server",
  unknown: "Unchecked",
};
const STATE_HELP: Record<EmailState, string> = {
  found: "This address is published on the company's website.",
  guessed: "Built from the name (first.last). The domain accepts email, but this address is not confirmed.",
  role_address: "A shared inbox for the company, not a named person.",
  no_mail_server: "This domain does not accept email, so nothing can be sent to it.",
  unknown: "The domain could not be checked. The address is a guess.",
};

export default function PeoplePanel({ lead, onChanged }: { lead: Lead; onChanged?: () => void }) {
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<{ err: boolean; text: string } | null>(null);

  const load = useCallback(async () => {
    const { data, error } = await supabase.from("contacts").select("*").eq("lead_id", lead.id).order("is_primary", { ascending: false }).order("created_at");
    if (error) setMsg({ err: true, text: `${error.message}. Run db/phase4.sql in the Supabase SQL editor.` });
    else setContacts(data as Contact[]);
  }, [lead.id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function find() {
    setBusy("find");
    setMsg(null);
    try {
      const r = await post<{ contacts: Contact[] }>(`/leads/${lead.id}/people`);
      setMsg({ err: false, text: r.contacts.length ? `Found ${r.contacts.length} ${r.contacts.length === 1 ? "contact" : "contacts"}.` : "No named people or addresses were published on the website." });
      await load();
      onChanged?.();
    } catch (e) {
      setMsg({ err: true, text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  async function use(c: Contact) {
    setBusy(c.id);
    setMsg(null);
    try {
      const r = await post<{ draft_outdated: boolean }>(`/leads/${lead.id}/contacts/${c.id}/use`);
      setMsg({ err: false, text: r.draft_outdated ? `Emails now go to ${c.full_name}. The existing draft still greets the previous person, so rewrite it in the approval queue.` : `Emails now go to ${c.full_name}.` });
      await load();
      onChanged?.();
    } catch (e) {
      setMsg({ err: true, text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  const canFind = !!lead.domain;
  return (
    <div className="people">
      <h3>
        <span>People</span>
        <button className="btn small" disabled={busy !== null || !canFind} onClick={find} title={canFind ? undefined : "This lead has no website"}>
          {busy === "find" ? "Searching…" : contacts && contacts.length ? "Search again" : "Find people"}
        </button>
      </h3>
      {msg && <p className={`msg ${msg.err ? "err" : ""}`} role={msg.err ? "alert" : "status"}>{msg.text}</p>}
      {contacts === null ? (
        !msg && <p className="muted">Loading…</p>
      ) : contacts.length === 0 ? (
        <p className="muted">No one yet. Find people reads the company&apos;s own About and Team pages and lists the named staff and any published addresses.</p>
      ) : (
        <ul>
          {contacts.map((c) => (
            <li key={c.id}>
              <div className="who2">
                <div className="strong">{c.full_name}{c.role ? <span className="muted"> · {c.role}</span> : null}</div>
                <div className="em">{c.email ?? "No usable address"}</div>
                <div className="chipline">
                  <span className={`ch ${c.email_status}`} title={STATE_HELP[c.email_status]}>{STATE_LABEL[c.email_status]}</span>
                  {c.source === "seed" && <span className="ch demo" title="Fictional data for the demo">Demo data</span>}
                  {c.is_primary && <span className="ch primary">Writing to</span>}
                </div>
              </div>
              {!c.is_primary && c.email && (
                <button className="btn small" disabled={busy !== null} onClick={() => use(c)}>Write to them</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
