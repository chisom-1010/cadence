"use client";

import { Fragment, useState } from "react";
import type { Lead } from "../lib/types";
import PeoplePanel from "./PeoplePanel";

const LABEL: Record<string, string> = {
  new: "New",
  researching: "Researching…",
  researched: "Researched",
  no_data: "No website data",
  drafted: "Drafted",
  approved: "Approved",
  sent: "Sent",
  replied: "Replied",
  failed: "Failed",
};

function Fit({ score }: { score: number | null }) {
  if (score == null) return <span className="muted">–</span>;
  const tone = score >= 70 ? "hi" : score >= 40 ? "mid" : "lo";
  return (
    <span className="fit" title={`Fit score ${score} out of 100`}>
      <span className="bar"><span className={`fill ${tone}`} style={{ width: `${score}%` }} /></span>
      <span className="fitnum">{score}</span>
    </span>
  );
}

export default function LeadTable({
  leads,
  onResearch,
  onChanged,
  busyId,
  showCampaign = false,
}: {
  leads: Lead[];
  onResearch?: (id: string) => void;
  onChanged?: () => void;
  busyId?: string | null;
  showCampaign?: boolean;
}) {
  const [open, setOpen] = useState<string | null>(null);
  const cols = showCampaign ? 6 : 5;

  return (
    <div className="tablewrap">
      <table className="leads">
        <thead>
          <tr>
            <th>Company</th>
            {showCampaign && <th>Campaign</th>}
            <th>Writing to</th>
            <th>Fit</th>
            <th>Status</th>
            <th><span className="sr">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {leads.map((l) => (
            <Fragment key={l.id}>
              <tr className={open === l.id ? "open" : ""}>
                <td>
                  <div className="strong">{l.company_name}</div>
                  <div className="muted">{l.domain ?? "no website"}</div>
                </td>
                {showCampaign && <td>{l.campaigns?.name ?? ""}</td>}
                <td>
                  <div>{l.contact_name ?? <span className="muted">–</span>}</div>
                  {l.contact_role && <div className="muted">{l.contact_role}</div>}
                </td>
                <td><Fit score={l.fit_score} /></td>
                <td><span className={`st ${l.status}`}>{LABEL[l.status] ?? l.status}</span></td>
                <td className="actions">
                  <div className="actbtns">
                    {onResearch && ["new", "failed", "no_data", "researched"].includes(l.status) && (
                      <button className="btn small" disabled={busyId === l.id} onClick={() => onResearch(l.id)}>
                        {busyId === l.id ? "Working…" : l.status === "new" ? "Research" : "Redo"}
                      </button>
                    )}
                    <button className="btn small quiet" aria-expanded={open === l.id} onClick={() => setOpen(open === l.id ? null : l.id)}>
                      {open === l.id ? "Hide" : "Details"}
                    </button>
                  </div>
                </td>
              </tr>
              {open === l.id && (
                <tr className="detail">
                  <td colSpan={cols}>
                    <div className="detail-grid">
                      <dl className="facts">
                        {l.research_summary && (<><dt>What they do</dt><dd>{l.research_summary}</dd></>)}
                        {l.fit_reason && (<><dt>Why this score</dt><dd>{l.fit_reason}</dd></>)}
                        {l.personalization_hook && (<><dt>Opening hook</dt><dd>{l.personalization_hook}</dd></>)}
                        {l.contact_email && (<><dt>Email</dt><dd>{l.contact_email}</dd></>)}
                        {l.error && (<><dt>Problem</dt><dd className="errtext">{l.error}</dd></>)}
                        <dt>Source</dt><dd>{l.source === "seed" ? "Demo data (fictional)" : l.source === "csv" ? "CSV import" : "Web search"}</dd>
                      </dl>
                      <PeoplePanel lead={l} onChanged={onChanged} />
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
