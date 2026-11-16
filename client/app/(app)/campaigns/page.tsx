"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { supabase } from "../../../lib/supabase";
import { errorText, post } from "../../../lib/api";
import type { Campaign } from "../../../lib/types";

type Row = Campaign & { leads: { count: number }[] };

export default function Campaigns() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [showForm, setShowForm] = useState<boolean | null>(null);
  const [name, setName] = useState("");
  const [pitch, setPitch] = useState("");
  const [desc, setDesc] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    supabase
      .from("campaigns")
      .select("*, leads(count)")
      .order("created_at", { ascending: false })
      .then(({ data, error }) => {
        if (error) setLoadError(error.message);
        else setRows(data as Row[]);
      });
  }, []);

  const formOpen = showForm ?? (rows !== null && rows.length === 0);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const out = await post<{ campaign: Campaign; warning: string | null }>("/campaigns", {
        name,
        product_pitch: pitch,
        icp_description: desc,
      });
      router.push(`/campaigns/${out.campaign.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Campaigns</h1>
          <p className="sub">A campaign is one product aimed at one kind of customer.</p>
        </div>
        <button className="btn primary" onClick={() => setShowForm(!formOpen)}>{formOpen ? "Cancel" : "New campaign"}</button>
      </header>

      {formOpen && (
        <form className="panel panel-pad form" onSubmit={create}>
          <div className="field">
            <label htmlFor="name">Name</label>
            <input id="name" required maxLength={120} placeholder="West Africa logistics, Q4" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="pitch">What you sell</label>
            <textarea id="pitch" rows={2} maxLength={2000} placeholder="Route planning software that cuts empty return trips" value={pitch} onChange={(e) => setPitch(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="desc">Who you want to reach</label>
            <textarea id="desc" required rows={3} minLength={3} maxLength={2000} placeholder="Small and mid-sized freight companies in Togo, Benin and Ghana with their own trucks" value={desc} onChange={(e) => setDesc(e.target.value)} />
            <span className="hint">One or two sentences are enough. The AI turns this into a profile you can check and edit.</span>
          </div>
          {error && <p className="msg err" role="alert">{error}</p>}
          <div><button className="btn primary" type="submit" disabled={busy}>{busy ? "Creating…" : "Create campaign"}</button></div>
        </form>
      )}

      <div className="panel panel-pad">
        {loadError && <p className="msg err">{loadError}. Run db/schema.sql in the Supabase SQL editor.</p>}
        {rows === null && !loadError && <p className="muted">Loading…</p>}
        {rows?.length === 0 && <p className="empty">No campaigns yet. Describe what you sell and who you want to reach to start.</p>}
        {rows && rows.length > 0 && (
          <ul className="camp-list">
            {rows.map((c) => (
              <li key={c.id}>
                <Link href={`/campaigns/${c.id}`}>
                  <span className="strong">{c.name}</span>
                  <span className="s">{c.icp?.summary ?? "Profile not generated yet"}</span>
                  <span className="meta"><span className="tag">{c.leads?.[0]?.count ?? 0} leads</span></span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
