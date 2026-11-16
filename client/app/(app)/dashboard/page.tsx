"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "../../../lib/supabase";
import { api, API_URL } from "../../../lib/api";
import { stageCounts } from "../../../lib/stages";
import type { Me } from "../../../lib/types";
import Pipeline from "../../../components/Pipeline";

type State = "checking" | "ok" | "fail";
type Check = { state: State; detail: string };

type Totals = {
  leadStatuses: string[];
  emailStatuses: string[];
  hot: number;
  unlabelled: number;
};

export default function Dashboard() {
  const [t, setT] = useState<Totals | null>(null);
  const [loadError, setLoadError] = useState("");
  const [db, setDb] = useState<Check>({ state: "checking", detail: "Reading your tables…" });
  const [health, setHealth] = useState<Check>({ state: "checking", detail: "Contacting the API…" });
  const [auth, setAuth] = useState<Check>({ state: "checking", detail: "Verifying your token…" });
  const [mail, setMail] = useState<Check>({ state: "checking", detail: "Checking the mail settings…" });

  const run = useCallback(async () => {
    setHealth({ state: "checking", detail: "Contacting the API…" });
    setAuth({ state: "checking", detail: "Verifying your token…" });
    setMail({ state: "checking", detail: "Checking the mail settings…" });

    const [leads, emails, replies] = await Promise.all([
      supabase.from("leads").select("status"),
      supabase.from("emails").select("status"),
      supabase.from("replies").select("is_hot, label"),
    ]);
    const err = leads.error ?? emails.error ?? replies.error;
    if (err) {
      setLoadError(err.message);
      setDb({ state: "fail", detail: `${err.message}. Run db/schema.sql in the Supabase SQL editor.` });
    } else {
      setLoadError("");
      setDb({ state: "ok", detail: "All tables answer." });
      setT({
        leadStatuses: (leads.data ?? []).map((r) => r.status as string),
        emailStatuses: (emails.data ?? []).map((r) => r.status as string),
        hot: (replies.data ?? []).filter((r) => r.is_hot).length,
        unlabelled: (replies.data ?? []).filter((r) => !r.label).length,
      });
    }

    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 60000);
    try {
      const r = await fetch(`${API_URL}/health`, { signal: ctrl.signal });
      setHealth(r.ok
        ? { state: "ok", detail: `${API_URL} responded.` }
        : { state: "fail", detail: `${API_URL}/health returned ${r.status}. Check the server logs and its Supabase keys.` });
    } catch {
      setHealth({ state: "fail", detail: `No answer from ${API_URL}. Start the server, and check NEXT_PUBLIC_API_URL.` });
    } finally {
      clearTimeout(timer);
    }

    try {
      const me = await api<Me>("/me");
      setAuth({ state: "ok", detail: `Signed in as ${me.email}.` });
      setMail(!me.mail_configured
        ? { state: "fail", detail: "Add MAILTRAP_API_TOKEN and SENDER_EMAIL to the server's .env, then restart it." }
        : me.demo_mode
          ? { state: "ok", detail: `Demo mode: every email is delivered to ${me.demo_recipient}.` }
          : { state: "ok", detail: "Live mode: emails go to the lead's own address." });
    } catch (e) {
      setAuth({ state: "fail", detail: `The server rejected the token: ${(e as Error).message}` });
      setMail({ state: "fail", detail: "Unknown until the server accepts your login." });
    }
  }, []);

  useEffect(() => {
    void run();
  }, [run]);

  const n = (list: string[] | undefined, s: string) => (list ?? []).filter((x) => x === s).length;
  const waitingResearch = (t?.leadStatuses ?? []).filter((s) => s === "new" || s === "failed").length;
  const needs = t
    ? [
        { n: n(t.emailStatuses, "draft"), what: "drafts to review", why: "Read each email, edit it if you want, then approve or reject.", href: "/queue", go: "Open the queue" },
        { n: n(t.emailStatuses, "approved"), what: "approved emails ready to send", why: "Approved, but not sent yet.", href: "/queue", go: "Send them" },
        { n: t.hot, what: "hot leads", why: "These people replied with clear interest. Answer them first.", href: "/replies", go: "Read replies", hot: true },
        { n: n(t.emailStatuses, "failed"), what: "emails that failed to send", why: "The error is shown on the email.", href: "/queue", go: "See why" },
        { n: waitingResearch, what: "leads waiting for research", why: "Research scores them and finds what to say.", href: "/campaigns", go: "Open campaigns" },
      ].filter((x) => x.n > 0)
    : [];

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Today</h1>
          <p className="sub">Where every lead stands, and what needs you.</p>
        </div>
      </header>

      {loadError && <p className="msg err" role="alert">{loadError}</p>}

      <Pipeline steps={stageCounts((t?.leadStatuses ?? []).map((status) => ({ status })))} />

      <div className="panel panel-pad">
        <div className="sect-head"><h2>Needs you</h2></div>
        {t === null ? (
          <p className="muted">Loading…</p>
        ) : needs.length === 0 ? (
          <p className="empty">
            {t.leadStatuses.length === 0
              ? <>Nothing yet. <Link href="/campaigns" className="link">Start a campaign</Link> to find your first leads.</>
              : "Nothing needs you right now."}
          </p>
        ) : (
          <ul className="needs">
            {needs.map((x) => (
              <li key={x.what}>
                <Link href={x.href}>
                  <span className={`big ${"hot" in x && x.hot ? "hot" : ""}`}>{x.n}</span>
                  <span>
                    <span className="what">{x.what}</span>
                    <span className="why" style={{ display: "block" }}>{x.why}</span>
                  </span>
                  <span className="go">{x.go}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="sect-head">
          <h2>System</h2>
          <button className="btn small quiet" onClick={run}>Check again</button>
        </div>
        <ul className="sys">
          {([["Database", db], ["API server", health], ["API login", auth], ["Email sending", mail]] as const).map(([name, c]) => (
            <li key={name}>
              <span className={`dot ${c.state}`} aria-hidden="true" />
              <span className="name">{name}</span>
              <span className="detail">{c.detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
