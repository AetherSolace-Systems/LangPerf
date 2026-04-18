import type { HeuristicHit } from "@/lib/triage";
import { HeuristicBadge } from "./heuristic-badge";

export function HeuristicHitsPanel({ hits }: { hits: HeuristicHit[] }) {
  if (hits.length === 0) return null;
  return (
    <section className="space-y-2 rounded-lg bg-warm-fog/5 p-3 ring-1 ring-warm-fog/10">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-warm-fog/60">Flags</h3>
      <ul className="space-y-1">
        {hits.map((h, i) => (
          <li key={`${h.signature}-${i}`} className="flex items-center justify-between gap-2 text-xs">
            <HeuristicBadge heuristic={h.heuristic} />
            <span className="font-mono text-[0.65rem] text-warm-fog/40">{h.signature}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
