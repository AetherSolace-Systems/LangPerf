import Link from "next/link";

import type { Cluster } from "@/lib/triage";
import { HeuristicBadge } from "./heuristic-badge";

export function ClusterCard({ cluster }: { cluster: Cluster }) {
  return (
    <div className="rounded-lg border border-warm-fog/10 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-warm-fog">{cluster.size} trajectories share this shape</p>
          <div className="mt-2 flex flex-wrap gap-1">
            {cluster.heuristics.map((h) => (
              <HeuristicBadge key={h} heuristic={h.split(":")[0]} />
            ))}
          </div>
          <p className="mt-1 font-mono text-[0.65rem] text-warm-fog/40">{cluster.signature}</p>
        </div>
        <Link
          href={`/t/${cluster.trajectory_ids[0]}`}
          className="shrink-0 rounded bg-aether-teal/10 px-3 py-1 text-xs text-aether-teal"
        >
          Open first
        </Link>
      </div>
    </div>
  );
}
