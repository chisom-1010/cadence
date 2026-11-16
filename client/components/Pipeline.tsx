import type { StageKey } from "../lib/stages";

type Step = { key: StageKey; label: string; count: number };

/** The pipeline as a row of stages. Each bar shows what share of all leads reached that stage. */
export default function Pipeline({
  steps,
  active,
  onPick,
}: {
  steps: Step[];
  active?: StageKey | null;
  onPick?: (key: StageKey | null) => void;
}) {
  const total = Math.max(steps[0]?.count ?? 0, 1);
  return (
    <div className="ribbon" role="group" aria-label="Pipeline">
      {steps.map((s) => (
        <button
          key={s.key}
          type="button"
          className="seg-step"
          aria-pressed={active === s.key}
          disabled={!onPick}
          onClick={() => onPick?.(active === s.key ? null : s.key)}
          title={onPick ? `Show leads that reached "${s.label}"` : undefined}
        >
          <span className="n">{s.count}</span>
          <span className="l">{s.label}</span>
          <span className="track" aria-hidden="true">
            <span className="fill" style={{ width: `${(s.count / total) * 100}%` }} />
          </span>
        </button>
      ))}
    </div>
  );
}
