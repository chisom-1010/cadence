"use client";

import { useCallback, useEffect, useState } from "react";
import { supabase } from "../../../lib/supabase";
import { errorText, post } from "../../../lib/api";
import type { Lead } from "../../../lib/types";
import LeadTable from "../../../components/LeadTable";

export default function Leads() {
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [status, setStatus] = useState("all");

  const load = useCallback(async () => {
    const { data, error } = await supabase
      .from("leads")
      .select("*, campaigns(name)")
      .order("fit_score", { ascending: false, nullsFirst: false })
      .order("created_at", { ascending: false });
    if (error) setError(error.message);
    else setLeads(data as Lead[]);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function researchOne(id: string) {
    setBusyId(id);
    setError("");
    try {
      await post(`/leads/${id}/research`);
      await load();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusyId(null);
    }
  }

  const shown = (leads ?? []).filter((l) => status === "all" || l.status === status);

  return (
    <section className="page">
      <header className="page-head">
        <div>
          <h1>Leads</h1>
          <p className="sub">Every company across your campaigns, best fit first.</p>
        </div>
        <label className="inline">
          <span className="muted">Show</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
            <option value="all">All leads</option>
            <option value="new">New</option>
            <option value="researched">Researched</option>
            <option value="drafted">Drafted</option>
            <option value="approved">Approved</option>
            <option value="sent">Sent</option>
            <option value="replied">Replied</option>
            <option value="no_data">No website data</option>
            <option value="failed">Failed</option>
          </select>
        </label>
      </header>
      <div className="panel panel-pad">
        {error && <p className="msg err" role="alert">{error}</p>}
        {leads === null && !error && <p className="muted">Loading…</p>}
        {leads && shown.length === 0 && <p className="empty">No leads here. Open a campaign to find or import some.</p>}
        {shown.length > 0 && <LeadTable leads={shown} onResearch={researchOne} onChanged={load} busyId={busyId} showCampaign />}
      </div>
    </section>
  );
}
