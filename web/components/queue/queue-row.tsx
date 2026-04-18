import Link from "next/link";

import type { QueueItem } from "@/lib/triage";
import { HeuristicBadge } from "./heuristic-badge";

export function QueueRow({ item }: { item: QueueItem }) {
  return (
    <Link
      href={`/t/${item.trajectory_id}`}
      className="flex items-start justify-between gap-4 rounded-lg border border-warm-fog/10 p-3 transition hover:border-aether-teal"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-warm-fog">{item.name || item.service_name}</p>
        <p className="mt-0.5 text-xs text-warm-fog/50">
          {item.service_name} · {item.started_at ? new Date(item.started_at).toLocaleString() : "—"}
        </p>
        <div className="mt-2 flex flex-wrap gap-1">
          {Array.from(new Set(item.hits.map((h) => h.heuristic))).map((h) => (
            <HeuristicBadge key={h} heuristic={h} />
          ))}
        </div>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-sm text-aether-teal">{item.score.toFixed(1)}</p>
        <p className="text-[0.65rem] text-warm-fog/40">score</p>
      </div>
    </Link>
  );
}
