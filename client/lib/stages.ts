import type { Lead } from "./types";

/** The pipeline every lead moves through. Counts are cumulative: a sent lead also counts as drafted. */
export const STAGES = [
  { key: "found", label: "Found", statuses: null },
  { key: "researched", label: "Researched", statuses: ["researched", "drafted", "approved", "sent", "replied"] },
  { key: "drafted", label: "Drafted", statuses: ["drafted", "approved", "sent", "replied"] },
  { key: "approved", label: "Approved", statuses: ["approved", "sent", "replied"] },
  { key: "sent", label: "Sent", statuses: ["sent", "replied"] },
  { key: "replied", label: "Replied", statuses: ["replied"] },
] as const;

export type StageKey = (typeof STAGES)[number]["key"];

export function reached(status: string, key: StageKey): boolean {
  const st = STAGES.find((s) => s.key === key)!;
  return st.statuses === null || (st.statuses as readonly string[]).includes(status);
}

export function stageCounts(leads: Pick<Lead, "status">[]) {
  return STAGES.map((s) => ({ key: s.key, label: s.label, count: leads.filter((l) => reached(l.status, s.key)).length }));
}
