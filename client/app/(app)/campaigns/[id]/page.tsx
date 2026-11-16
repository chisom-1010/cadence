"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { supabase } from "../../../../lib/supabase";
import { errorText, post } from "../../../../lib/api";
import { reached, stageCounts, type StageKey } from "../../../../lib/stages";
import type { Campaign, Competitor, Lead } from "../../../../lib/types";
import LeadTable from "../../../../components/LeadTable";
import Pipeline from "../../../../components/Pipeline";

type Msg = { kind: "ok" | "err"; text: string } | null;
const ACTIVE = ["new", "researching"];
const MIN_FIT = 40; // must match MIN_FIT_TO_DRAFT on the server

function Row({ label, items }: { label: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <>
      <dt>{label}</dt>
      <dd>{items.map((i) => (<span className="tag" key={i}>{i}</span>))}</dd>
    </>
  );
}

export default function CampaignPage() {
  const { id } = useParams<{ id: string }>();
  const [campaign, setCampaign] = useState<Campaign | null | undefined>(undefined);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [withPeople, setWithPeople] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [busyLead, setBusyLead] = useState<string | null>(null);
  const [watching, setWatching] = useState(false);
  const [draftUntil, setDraftUntil] = useState(0);
  const [peopleUntil, setPeopleUntil] = useState(0);
  const [msg, setMsg] = useState<Msg>(null);
  const [editing, setEditing] = useState(false);
  const [pitch, setPitch] = useState("");
  const [desc, setDesc] = useState("");
  const [stage, setStage] = useState<StageKey | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    const [c, l, p] = await Promise.all([
      supabase.from("campaigns").select("*").eq("id", id).maybeSingle(),
      supabase.from("leads").select("*").eq("campaign_id", id).order("fit_score", { ascending: false, nullsFirst: false }).order("created_at"),
      supabase.from("contacts").select("lead_id").eq("campaign_id", id),
    ]);
    if (c.error || l.error) setMsg({ kind: "err", text: (c.error ?? l.error)!.message });
    setCampaign((c.data as Campaign | null) ?? null);
    setLeads((l.data as Lead[]) ?? []);
    setWithPeople(new Set(((p.data as { lead_id: string }[]) ?? []).map((r) => r.lead_id))); // empty until db/phase4.sql has been run
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  /* Background jobs: refresh every 3 seconds while something is still running, and stop when it is done or time is up. */
  const pending = leads.some((l) => ACTIVE.includes(l.status));
  const good = leads.filter((l) => l.status === "researched" && (l.fit_score ?? 0) >= MIN_FIT);
  const draftLeft = good.length;
  const peopleLeft = good.filter((l) => !!l.domain && !withPeople.has(l.id)).length;
  const drafting = draftUntil > 0 && draftLeft > 0;
  const searchingPeople = peopleUntil > 0 && peopleLeft > 0;

  useEffect(() => {
    if (!watching) return;
    if (!pending) {
      setWatching(false);
      return;
    }
    const t = setInterval(() => void load(), 3000);
    return () => clearInterval(t);
  }, [watching, pending, load]);

  useEffect(() => {
    if (!drafting) return;
    const t = setInterval(() => {
      if (Date.now() > draftUntil) setDraftUntil(0);
      else void load();
    }, 3000);
    return () => clearInterval(t);
  }, [drafting, draftUntil, load]);

  useEffect(() => {
    if (!searchingPeople) return;
    const t = setInterval(() => {
      if (Date.now() > peopleUntil) setPeopleUntil(0);
      else void load();
    }, 3000);
    return () => clearInterval(t);
  }, [searchingPeople, peopleUntil, load]);

  async function run<T>(key: string, fn: () => Promise<T>, done: (r: T) => string) {
    setBusy(key);
    setMsg(null);
    try {
      const r = await fn();
      setMsg({ kind: "ok", text: done(r) });
      await load();
    } catch (e) {
      setMsg({ kind: "err", text: errorText(e) });
    } finally {
      setBusy(null);
    }
  }

  const discover = () =>
    run("discover", () => post<{ added: number; already_known: number; results_read: number }>(`/campaigns/${id}/discover`),
      (r) => `Read ${r.results_read} search results. Added ${r.added} lead${r.added === 1 ? "" : "s"}${r.already_known ? `, ${r.already_known} already known or competitors` : ""}.`);
  const seed = () =>
    run("seed", () => post<{ added: number }>(`/campaigns/${id}/seed`), (r) => (r.added ? `Added ${r.added} fictional demo leads.` : "The demo leads are already here."));
  const researchAll = (force = false) =>
    run("research", () => post<{ queued: number }>(`/campaigns/${id}/research${force ? "?force=true" : ""}`), (r) => {
      if (r.queued) setWatching(true);
      return r.queued ? `Researching ${r.queued} lead${r.queued === 1 ? "" : "s"} in the background. This page updates as each finishes.` : "Nothing waiting. Every lead has been researched.";
    });
  const peopleAll = () =>
    run("people", () => post<{ queued: number }>(`/campaigns/${id}/people`), (r) => {
      if (r.queued) setPeopleUntil(Date.now() + 30_000 + r.queued * 25_000);
      return r.queued ? `Looking for people at ${r.queued} compan${r.queued === 1 ? "y" : "ies"} in the background.` : `Nothing to search. People are found for researched leads with a fit score of ${MIN_FIT} or more.`;
    });
  const draftAll = () =>
    run("draft", () => post<{ queued: number; min_fit: number }>(`/campaigns/${id}/draft`), (r) => {
      if (r.queued) setDraftUntil(Date.now() + 20_000 + r.queued * 15_000);
      return r.queued
        ? `Writing ${r.queued} draft${r.queued === 1 ? "" : "s"} in the background. They appear in the approval queue as they finish.`
        : `Nothing to draft. Drafts are written for researched leads with a fit score of ${r.min_fit} or more.`;
    });
  const competitorsFind = () =>
    run("competitors", () => post<{ competitors: Competitor[] }>(`/campaigns/${id}/competitors`),
      (r) => (r.competitors.length ? `Found ${r.competitors.length} competitor${r.competitors.length === 1 ? "" : "s"}. They are kept out of your lead list.` : "No competitors were found in the search results."));
  const regenerate = () =>
    run("icp", () => post(`/campaigns/${id}/icp`, editing ? { product_pitch: pitch, icp_description: desc } : undefined),
      () => { setEditing(false); return "Profile updated."; });

  async function researchOne(leadId: string) {
    setBusyLead(leadId);
    setMsg(null);
    try {
      await post(`/leads/${leadId}/research`);
      await load();
    } catch (e) {
      setMsg({ kind: "err", text: errorText(e) });
    } finally {
      setBusyLead(null);
    }
  }

  async function importCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const text = await file.text();
    await run("import", () => post<{ added: number; skipped: number }>(`/campaigns/${id}/leads/import`, { csv: text }),
      (r) => `Imported ${r.added} lead${r.added === 1 ? "" : "s"}${r.skipped ? `, skipped ${r.skipped} (missing company or bad domain, or duplicates)` : ""}.`);
  }

  if (campaign === undefined) return <p className="muted">Loading…</p>;
  if (campaign === null)
    return (
      <section className="page">
        <h1>Campaign not found</h1>
        <p className="muted">It may have been deleted. <Link href="/campaigns" className="link">Back to campaigns</Link></p>
      </section>
    );

  const icp = campaign.icp;
  const count = (s: string) => leads.filter((l) => l.status === s).length;
  const waiting = leads.filter((l) => ["new", "failed"].includes(l.status)).length;
  const inQueue = count("drafted");
  const disabled = busy !== null;
  const stuck = watching ? 0 : count("researching");
  const next = !icp ? "icp" : leads.length === 0 ? "discover" : waiting > 0 ? "research" : peopleLeft > 0 ? "people" : draftLeft > 0 ? "draft" : inQueue > 0 ? "queue" : "";
  const cls = (k: string) => `btn small${next === k ? " primary" : ""}`;
  const shown = stage ? leads.filter((l) => reached(l.status, stage)) : leads;
  const stageLabel = stage ? stageCounts([]).find((s) => s.key === stage)?.label : "";
  const comps = campaign.competitors ?? [];

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <p className="crumb"><Link href="/campaigns" className="link">Campaigns</Link></p>
          <h1>{campaign.name}</h1>
        </div>
        {inQueue > 0 && <Link href="/queue" className={`btn${next === "queue" ? " primary" : ""}`}>Review {inQueue} draft{inQueue === 1 ? "" : "s"}</Link>}
      </header>

      <Pipeline steps={stageCounts(leads)} active={stage} onPick={setStage} />

      <div className="panel panel-pad">
        <div className="sect-head">
          <h2>Ideal customer</h2>
          <div className="btnrow">
            <button className="btn small quiet" disabled={disabled} onClick={() => { setPitch(campaign.product_pitch); setDesc(campaign.icp_description); setEditing(!editing); }}>
              {editing ? "Cancel" : "Edit"}
            </button>
            {!editing && <button className={cls("icp")} disabled={disabled} onClick={regenerate}>{busy === "icp" ? "Working…" : icp ? "Regenerate" : "Generate"}</button>}
          </div>
        </div>
        {editing ? (
          <div className="form">
            <div className="field"><label htmlFor="e-pitch">What you sell</label><textarea id="e-pitch" rows={2} value={pitch} onChange={(e) => setPitch(e.target.value)} /></div>
            <div className="field"><label htmlFor="e-desc">Who you want to reach</label><textarea id="e-desc" rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} /></div>
            <div><button className="btn primary" disabled={disabled || desc.trim().length < 3} onClick={regenerate}>{busy === "icp" ? "Working…" : "Save and regenerate"}</button></div>
          </div>
        ) : icp ? (
          <div className="profile">
            <p className="summary">{icp.summary}</p>
            <dl className="deflist">
              <Row label="Industries" items={icp.industries} />
              <Row label="Regions" items={icp.regions} />
              <Row label="Company size" items={icp.company_size ? [icp.company_size] : []} />
              <Row label="Who to contact" items={icp.target_roles} />
              <Row label="Pain points" items={icp.pain_points} />
              <Row label="Keywords" items={icp.keywords} />
              <Row label="Avoid" items={icp.exclusions} />
            </dl>
          </div>
        ) : (
          <p className="empty">No profile yet. It could not be generated when the campaign was created. Check the server&apos;s LLM settings, then press Generate.</p>
        )}
      </div>

      <div className="panel panel-pad">
        <div className="sect-head">
          <h2>Competitors <span className="count">{comps.length}</span></h2>
          <button className="btn small" disabled={disabled || !campaign.product_pitch} onClick={competitorsFind} title={campaign.product_pitch ? undefined : "Add what you sell first"}>
            {busy === "competitors" ? "Searching…" : comps.length ? "Search again" : "Find competitors"}
          </button>
        </div>
        {comps.length === 0 ? (
          <p className="empty" style={{ padding: 0 }}>Finds products like yours from a web search. Companies found here are never added as leads.</p>
        ) : (
          <ul className="comp">
            {comps.map((c) => (
              <li key={c.domain}>
                <div className="strong">{c.name}</div>
                <div className="d">{c.domain}</div>
                {c.note && <div className="note">{c.note}</div>}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="panel panel-pad">
        <div className="sect-head">
          <h2>Leads <span className="count">{leads.length}</span></h2>
          <div className="btnrow">
            <button className={cls("discover")} disabled={disabled || !icp} onClick={discover}>{busy === "discover" ? "Searching…" : "Find leads"}</button>
            <button className="btn small" disabled={disabled} onClick={seed}>{busy === "seed" ? "Adding…" : "Add demo leads"}</button>
            <button className="btn small" disabled={disabled} onClick={() => fileRef.current?.click()}>{busy === "import" ? "Importing…" : "Import CSV"}</button>
            <button className={cls("research")} disabled={disabled || !icp || waiting === 0} onClick={() => researchAll()}>{busy === "research" ? "Starting…" : `Research ${waiting || ""}`.trim()}</button>
            <button className={cls("people")} disabled={disabled || searchingPeople || peopleLeft === 0} onClick={peopleAll}>{busy === "people" ? "Starting…" : searchingPeople ? "Finding people…" : `Find people${peopleLeft ? ` for ${peopleLeft}` : ""}`}</button>
            <button className={cls("draft")} disabled={disabled || drafting || draftLeft === 0} onClick={draftAll}>{busy === "draft" ? "Starting…" : drafting ? "Drafting…" : `Draft ${draftLeft || ""}`.trim()}</button>
            {stuck > 0 && <button className="btn small" disabled={disabled} onClick={() => researchAll(true)} title="These were started but never finished, for example because the server restarted">{`Retry ${stuck} stuck`}</button>}
            <input ref={fileRef} type="file" accept=".csv,text/csv" hidden onChange={importCsv} aria-label="CSV file" />
          </div>
        </div>
        {msg && <p className={`msg ${msg.kind === "err" ? "err" : ""}`} role={msg.kind === "err" ? "alert" : "status"}>{msg.text}</p>}
        {(watching || drafting || searchingPeople) && <p className="hint" aria-live="polite">Working in the background. This list updates by itself.</p>}
        {stage && (
          <p className="stagebar">
            Showing the {shown.length} lead{shown.length === 1 ? "" : "s"} that reached &quot;{stageLabel}&quot;.
            <button className="btn small quiet" onClick={() => setStage(null)}>Show all</button>
          </p>
        )}
        {leads.length === 0 ? (
          <p className="empty">No leads yet. Find leads from a web search, import a CSV with the columns company, website, contact name, role and email, or add the fictional demo set to try the flow.</p>
        ) : (
          <LeadTable leads={shown} onResearch={researchOne} onChanged={load} busyId={busyLead} />
        )}
      </div>
    </section>
  );
}
