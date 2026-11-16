"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { supabase } from "../../../lib/supabase";
import { errorText, post } from "../../../lib/api";
import type { Reply, ReplyLabel } from "../../../lib/types";

const LABEL: Record<ReplyLabel, string> = {
  interested: "Interested",
  question: "Has a question",
  not_interested: "Not interested",
  out_of_office: "Out of office",
  unsubscribe: "Unsubscribe",
};

type SentLead = { id: string; company_name: string; status: string };
type Msg = { kind: "ok" | "err"; text: string } | null;

export default function Replies() {
  const [replies, setReplies] = useState<Reply[] | null>(null);
  const [leads, setLeads] = useState<SentLead[]>([]);
  const [filter, setFilter] = useState<"all" | "hot" | ReplyLabel>("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<Msg>(null);
  const [leadId, setLeadId] = useState("");
  const [text, setText] = useState("");

  const load = useCallback(async () => {
    const [r, l] = await Promise.all([
      supabase.from("replies").select("*, leads(company_name, contact_name, domain)").order("received_at", { ascending: false }),
      supabase.from("leads").select("id, company_name, status").in("status", ["sent", "replied"]).order("company_name"),
    ]);
    if (r.error || l.error) setMsg({ kind: "err", text: (r.error ?? l.error)!.message });
    setReplies((r.data as unknown as Reply[]) ?? []);
    setLeads((l.data as SentLead[]) ?? []);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sorted = useMemo(
    () => [...(replies ?? [])].sort((a, b) => Number(b.is_hot) - Number(a.is_hot) || +new Date(b.received_at) - +new Date(a.received_at)),
    [replies],
  );
  const shown = sorted.filter((r) => filter === "all" || (filter === "hot" ? r.is_hot : r.label === filter));
  const hot = (replies ?? []).filter((r) => r.is_hot).length;

  async function relabel(id: string) {
    setBusy(id);
    setMsg(null);
    try {
      await post(`/replies/${id}/classify`);
      await load();
    } catch (e) {
      setMsg({ kind: "err", text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  async function logReply(e: React.FormEvent) {
    e.preventDefault();
    setBusy("log");
    setMsg(null);
    try {
      const r = await post<{ warning: string | null }>(`/leads/${leadId}/replies`, { body: text });
      setText("");
      setMsg(r.warning
        ? { kind: "err", text: `Saved, but it could not be labelled: ${r.warning}` }
        : { kind: "ok", text: "Reply saved and labelled." });
      await load();
    } catch (err) {
      setMsg({ kind: "err", text: errorText(err) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Replies</h1>
          <p className="sub">{hot ? `${hot} hot lead${hot === 1 ? "" : "s"} waiting for an answer. ` : ""}Each reply is read and labelled by the AI. Hot means clear buying interest.</p>
        </div>
        <label className="inline">
          <span className="muted">Show</span>
          <select value={filter} onChange={(e) => setFilter(e.target.value as typeof filter)} aria-label="Filter replies">
            <option value="all">All replies</option>
            <option value="hot">Hot leads only</option>
            {(Object.keys(LABEL) as ReplyLabel[]).map((k) => (<option key={k} value={k}>{LABEL[k]}</option>))}
          </select>
        </label>
      </header>

      {msg && <p className={`msg ${msg.kind === "err" ? "err" : ""}`} role={msg.kind === "err" ? "alert" : "status"}>{msg.text}</p>}

      <div className="panel panel-pad">
        {replies === null ? (
          <p className="muted">Loading…</p>
        ) : shown.length === 0 ? (
          <p className="empty">
            {replies.length === 0
              ? "No replies yet. Send an email from the approval queue, then use Simulate reply on the Sent tab to see how replies are labelled, or log a real one below."
              : "No replies match this filter."}
          </p>
        ) : (
          <ul>
            {shown.map((r) => (
              <li key={r.id} className={r.is_hot ? "reply hot" : "reply"}>
                <div className="reply-head">
                  <span className="strong">{r.leads?.company_name ?? "Unknown"}</span>
                  {r.leads?.contact_name && <span className="muted">{r.leads.contact_name}</span>}
                  {r.is_hot && <span className="hotflag">Hot lead</span>}
                  {r.label ? <span className={`lab ${r.label}`}>{LABEL[r.label]}</span> : <span className="lab">Not labelled</span>}
                  {r.simulated && <span className="muted" style={{ fontSize: 13 }}>simulated</span>}
                  <span className="when">{new Date(r.received_at).toLocaleString()}</span>
                </div>
                <p className="quote">{r.body}</p>
                {r.reason && <p className="muted" style={{ fontSize: 14 }}>Why: {r.reason}</p>}
                {!r.label && <div><button className="btn small" disabled={busy === r.id} onClick={() => relabel(r.id)}>{busy === r.id ? "Working…" : "Label with AI"}</button></div>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <form className="panel panel-pad form" onSubmit={logReply}>
        <div>
          <h2 style={{ fontSize: 17, fontWeight: 650 }}>Log a reply you received</h2>
          <p className="muted" style={{ marginTop: 4, fontSize: 14 }}>Replies arrive in the inbox of your sending address, not here. Paste one in and it is labelled the same way.</p>
        </div>
        <div className="field">
          <label htmlFor="lead">Which lead replied</label>
          <select id="lead" value={leadId} onChange={(e) => setLeadId(e.target.value)} required>
            <option value="">Choose a lead you emailed…</option>
            {leads.map((l) => (<option key={l.id} value={l.id}>{l.company_name}</option>))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="rtext">Their reply</label>
          <textarea id="rtext" rows={4} value={text} onChange={(e) => setText(e.target.value)} required />
        </div>
        <div><button className="btn primary" disabled={busy === "log" || !leadId || !text.trim()}>{busy === "log" ? "Saving…" : "Save and label"}</button></div>
      </form>
    </section>
  );
}
