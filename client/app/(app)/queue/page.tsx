"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "../../../lib/supabase";
import { api, errorText, post } from "../../../lib/api";
import type { Email, Me } from "../../../lib/types";

type Msg = { kind: "ok" | "err"; text: string } | null;
type Tab = "review" | "approved" | "sent" | "rejected";
type Act = "approve" | "reject" | "send" | "redraft";

const TABS: { key: Tab; label: string; statuses: Email["status"][] }[] = [
  { key: "review", label: "To review", statuses: ["draft", "failed"] },
  { key: "approved", label: "Approved", statuses: ["approved"] },
  { key: "sent", label: "Sent", statuses: ["sent"] },
  { key: "rejected", label: "Rejected", statuses: ["rejected"] },
];

const SAMPLES = [
  { key: "interested", label: "Interested" },
  { key: "question", label: "Asks a question" },
  { key: "not_interested", label: "Not interested" },
  { key: "out_of_office", label: "Out of office" },
  { key: "unsubscribe", label: "Unsubscribe" },
] as const;

const STATUS_LABEL: Record<Email["status"], string> = { draft: "Draft", approved: "Approved", rejected: "Rejected", sent: "Sent", failed: "Failed" };

function Fit({ score }: { score: number | null | undefined }) {
  if (score == null) return null;
  const tone = score >= 70 ? "hi" : score >= 40 ? "mid" : "lo";
  return (
    <span className="fit" title={`Fit score ${score} out of 100`}>
      <span className="bar"><span className={`fill ${tone}`} style={{ width: `${score}%` }} /></span>
      <span className="fitnum">{score}</span>
    </span>
  );
}

function Letter({
  email, me, busy, onAct, onSave, onSimulate,
}: {
  email: Email;
  me: Me | null;
  busy: boolean;
  onAct: (e: Email, a: Act) => void;
  onSave: (e: Email, subject: string, body: string) => Promise<boolean>;
  onSimulate: (e: Email, sample: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [subject, setSubject] = useState(email.subject);
  const [body, setBody] = useState(email.body);
  const [sample, setSample] = useState<string>("interested");
  const lead = email.leads;
  const s = email.status;
  const to = lead?.contact_email ?? "no address on file";
  const basis = [lead?.research_summary, lead?.personalization_hook, lead?.fit_reason].some(Boolean);

  return (
    <div>
      <article className="letter" aria-label={`Email to ${lead?.company_name ?? "lead"}`}>
        <div className="stripe" aria-hidden="true" />
        <div className="letter-body">
          <dl className="route">
            <dt>To</dt>
            <dd>{lead?.contact_name ? `${lead.contact_name} · ` : ""}{to} <span className="muted">at {lead?.company_name}</span></dd>
            {me?.demo_mode && s !== "rejected" && (<><dt>Goes to</dt><dd>{me.demo_recipient} <span className="muted">(demo mode)</span></dd></>)}
            <dt>Status</dt>
            <dd><span className={`st ${s === "failed" ? "failed" : s}`}>{STATUS_LABEL[s]}</span></dd>
          </dl>
          {editing ? (
            <div className="form edit" style={{ maxWidth: "none" }}>
              <div className="field">
                <label htmlFor={`sub-${email.id}`}>Subject</label>
                <input id={`sub-${email.id}`} value={subject} onChange={(e) => setSubject(e.target.value)} />
              </div>
              <div className="field">
                <label htmlFor={`body-${email.id}`}>Message</label>
                <textarea id={`body-${email.id}`} rows={12} value={body} onChange={(e) => setBody(e.target.value)} />
              </div>
            </div>
          ) : (
            <>
              <h2 className="subject">{email.subject}</h2>
              <div className="text">{email.body}</div>
            </>
          )}
          {s === "failed" && email.error && <p className="msg err" role="alert" style={{ marginTop: 14 }}>{email.error}</p>}
          {s === "sent" && (
            <p className="muted" style={{ marginTop: 14, fontSize: 14 }}>
              Delivered to {email.sent_to ?? "unknown"}{email.sent_at ? ` on ${new Date(email.sent_at).toLocaleString()}` : ""}.
              {lead?.status === "replied" && <> They replied. <Link href="/replies" className="link">Read the reply</Link></>}
            </p>
          )}
        </div>
        <div className="letter-foot">
          {editing ? (
            <>
              <button className="btn primary" disabled={busy || !subject.trim() || !body.trim()} onClick={async () => { if (await onSave(email, subject, body)) setEditing(false); }}>
                {s === "approved" ? "Save and review again" : "Save changes"}
              </button>
              <button className="btn quiet" disabled={busy} onClick={() => { setEditing(false); setSubject(email.subject); setBody(email.body); }}>Cancel</button>
            </>
          ) : (
            <>
              {(s === "draft" || s === "failed") && <button className="btn primary" disabled={busy} onClick={() => onAct(email, "approve")}>{s === "failed" ? "Approve again" : "Approve"}</button>}
              {s === "approved" && <button className="btn primary" disabled={busy} onClick={() => onAct(email, "send")}>Send now</button>}
              {["draft", "failed", "approved"].includes(s) && <button className="btn" disabled={busy} onClick={() => setEditing(true)}>Edit</button>}
              {["draft", "failed", "rejected"].includes(s) && <button className="btn" disabled={busy} onClick={() => onAct(email, "redraft")}>Rewrite with AI</button>}
              {["draft", "failed", "approved"].includes(s) && <button className="btn quiet danger" disabled={busy} onClick={() => onAct(email, "reject")}>Reject</button>}
              {s === "sent" && (
                <span className="inline">
                  <select value={sample} onChange={(e) => setSample(e.target.value)} aria-label="Sample reply type">
                    {SAMPLES.map((x) => (<option key={x.key} value={x.key}>{x.label}</option>))}
                  </select>
                  <button className="btn" disabled={busy} onClick={() => onSimulate(email, sample)}>Simulate reply</button>
                </span>
              )}
            </>
          )}
        </div>
      </article>
      {basis && (
        <aside className="basis" aria-label="What this email is based on">
          <h3>What this email is based on</h3>
          {lead?.research_summary && <p><span className="muted">From their website: </span>{lead.research_summary}</p>}
          {lead?.personalization_hook && <p><span className="muted">Opening line comes from: </span>{lead.personalization_hook}</p>}
          {lead?.fit_reason && <p><span className="muted">Why they fit: </span>{lead.fit_reason}</p>}
        </aside>
      )}
    </div>
  );
}

export default function Queue() {
  const [emails, setEmails] = useState<Email[] | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [tab, setTab] = useState<Tab>("review");
  const [selected, setSelected] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [bulk, setBulk] = useState<string | null>(null);
  const [watchUntil, setWatchUntil] = useState(0);
  const [msg, setMsg] = useState<Msg>(null);

  const load = useCallback(async () => {
    const { data, error } = await supabase
      .from("emails")
      .select("*, leads(company_name, domain, contact_name, contact_email, fit_score, status, research_summary, personalization_hook, fit_reason)")
      .order("created_at", { ascending: false });
    if (error) setMsg({ kind: "err", text: error.message });
    else setEmails(data as unknown as Email[]);
  }, []);

  useEffect(() => {
    void load();
    api<Me>("/me").then(setMe).catch(() => setMe(null));
  }, [load]);

  /* After "Send all", sending runs on the server. Refresh every 3 seconds until nothing is left approved. */
  const approvedLeft = (emails ?? []).some((e) => e.status === "approved");
  const watching = watchUntil > 0 && approvedLeft;
  useEffect(() => {
    if (!watchUntil || !approvedLeft) return;
    const t = setInterval(() => {
      if (Date.now() > watchUntil) setWatchUntil(0);
      else void load();
    }, 3000);
    return () => clearInterval(t);
  }, [watchUntil, approvedLeft, load]);

  async function act(e: Email, action: Act) {
    setBusyId(e.id);
    setMsg(null);
    try {
      if (action === "redraft") await post(`/leads/${e.lead_id}/draft`);
      else await post(`/emails/${e.id}/${action}`);
      if (action === "send") setMsg({ kind: "ok", text: `Sent to ${me?.demo_mode ? me.demo_recipient : (e.leads?.contact_email ?? "the lead")}.` });
      if (action === "redraft") setMsg({ kind: "ok", text: "Rewritten. Read it again before approving." });
      await load();
    } catch (err) {
      setMsg({ kind: "err", text: errorText(err) });
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function save(e: Email, subject: string, body: string): Promise<boolean> {
    setBusyId(e.id);
    setMsg(null);
    try {
      await api(`/emails/${e.id}`, { method: "PATCH", body: JSON.stringify({ subject, body }) });
      await load();
      return true;
    } catch (err) {
      setMsg({ kind: "err", text: errorText(err) });
      return false;
    } finally {
      setBusyId(null);
    }
  }

  async function simulate(e: Email, sample: string) {
    setBusyId(e.id);
    setMsg(null);
    try {
      const r = await post<{ warning: string | null }>(`/leads/${e.lead_id}/replies/simulate`, { sample });
      setMsg(r.warning
        ? { kind: "err", text: `Reply saved, but it could not be labelled: ${r.warning}` }
        : { kind: "ok", text: "Reply added and labelled. See it on the Replies page." });
      await load();
    } catch (err) {
      setMsg({ kind: "err", text: errorText(err) });
    } finally {
      setBusyId(null);
    }
  }

  async function approveAll() {
    setBulk("approve");
    setMsg(null);
    try {
      const r = await post<{ approved: number }>("/emails/approve-all");
      setMsg({ kind: "ok", text: `Approved ${r.approved} draft${r.approved === 1 ? "" : "s"}.` });
      await load();
    } catch (err) {
      setMsg({ kind: "err", text: errorText(err) });
    } finally {
      setBulk(null);
    }
  }

  async function sendAll() {
    setBulk("send");
    setMsg(null);
    try {
      const r = await post<{ queued: number }>("/emails/send-approved");
      if (r.queued) setWatchUntil(Date.now() + 15_000 + r.queued * 8_000);
      setMsg({ kind: "ok", text: r.queued ? `Sending ${r.queued} email${r.queued === 1 ? "" : "s"} in the background. This page updates as each one goes out.` : "Nothing approved to send." });
      await load();
    } catch (err) {
      setMsg({ kind: "err", text: errorText(err) });
    } finally {
      setBulk(null);
    }
  }

  const inTab = (t: Tab) => (emails ?? []).filter((e) => TABS.find((x) => x.key === t)!.statuses.includes(e.status));
  const shown = inTab(tab);
  const current = shown.find((e) => e.id === selected) ?? shown[0] ?? null;
  const drafts = (emails ?? []).filter((e) => e.status === "draft").length;

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Approval queue</h1>
          <p className="sub">Nothing is sent until you approve it.</p>
        </div>
        <div className="btnrow">
          {tab === "review" && drafts > 0 && <button className="btn" disabled={bulk !== null} onClick={approveAll}>{bulk === "approve" ? "Approving…" : `Approve all ${drafts}`}</button>}
          {tab === "approved" && inTab("approved").length > 0 && (
            <button className="btn primary" disabled={bulk !== null || watching} onClick={sendAll}>{bulk === "send" || watching ? "Sending…" : `Send all ${inTab("approved").length}`}</button>
          )}
        </div>
      </header>

      {me && (
        <p className={`banner ${me.mail_configured ? "" : "warn"}`} role="status">
          {!me.mail_configured
            ? "Sending is not set up yet. Add MAILTRAP_API_TOKEN and SENDER_EMAIL to the server's .env and restart it. You can still draft, edit and approve."
            : me.demo_mode
              ? <>Demo mode is on. Every email is delivered to {me.demo_recipient} instead of the lead, and says who it was meant for.</>
              : "Demo mode is off. Emails go to the lead's real address."}
        </p>
      )}
      {msg && <p className={`msg ${msg.kind === "err" ? "err" : ""}`} role={msg.kind === "err" ? "alert" : "status"}>{msg.text}</p>}

      <div className="tabs" role="tablist" aria-label="Email status">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className="tab" onClick={() => { setTab(t.key); setSelected(null); }}>
            {t.label}<span className="c">{inTab(t.key).length}</span>
          </button>
        ))}
      </div>

      {emails === null ? (
        <p className="muted">Loading…</p>
      ) : shown.length === 0 ? (
        <p className="empty">
          {tab === "review" && (emails.length === 0
            ? <>No drafts yet. Open a campaign, research its leads, then press Draft. <Link href="/campaigns" className="link">Go to campaigns</Link></>
            : "Nothing waiting for review.")}
          {tab === "approved" && "No approved emails. Approve a draft first."}
          {tab === "sent" && "Nothing sent yet."}
          {tab === "rejected" && "No rejected drafts."}
        </p>
      ) : (
        <div className="desk">
          <div className="qlist" role="list" aria-label="Emails">
            {shown.map((e) => (
              <button key={e.id} role="listitem" className="qitem" aria-current={current?.id === e.id} onClick={() => setSelected(e.id)}>
                <span className="top">
                  <span className="strong">{e.leads?.company_name ?? "Unknown"}</span>
                  <Fit score={e.leads?.fit_score} />
                </span>
                <span className="muted" style={{ fontSize: 13.5 }}>{e.leads?.contact_name ?? e.leads?.contact_email ?? "No contact"}</span>
                <span className="subj">{e.subject}</span>
              </button>
            ))}
          </div>
          {current && (
            <Letter key={current.id + current.status + current.subject + current.body} email={current} me={me} busy={busyId === current.id || bulk !== null} onAct={act} onSave={save} onSimulate={simulate} />
          )}
        </div>
      )}
    </section>
  );
}
