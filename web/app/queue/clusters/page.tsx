import { headers } from "next/headers";

import { ClusterCard } from "@/components/queue/cluster-card";
import { fetchClusters } from "@/lib/triage";

export const dynamic = "force-dynamic";

export default async function ClustersPage() {
  const cookie = headers().get("cookie") ?? "";
  const { clusters } = await fetchClusters(cookie);

  return (
    <main className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-semibold text-aether-teal">Clusters</h1>
        <p className="text-xs text-warm-fog/60">
          Trajectories grouped by the shape of their heuristic hits. Large clusters = recurring failure.
        </p>
      </header>
      <div className="space-y-2">
        {clusters.length === 0 ? (
          <p className="rounded-lg border border-dashed border-warm-fog/20 p-6 text-center text-sm text-warm-fog/50">
            No clusters yet.
          </p>
        ) : (
          clusters.map((c) => <ClusterCard key={c.id} cluster={c} />)
        )}
      </div>
    </main>
  );
}
