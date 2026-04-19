import Link from "next/link";
import { headers } from "next/headers";

import { AppShell } from "@/components/shell/app-shell";
import { Chip } from "@/components/ui/chip";
import { ClusterCard } from "@/components/queue/cluster-card";
import { fetchClusters } from "@/lib/triage";

export const dynamic = "force-dynamic";

export default async function ClustersPage() {
  const cookie = headers().get("cookie") ?? "";
  const { clusters } = await fetchClusters(cookie);

  return (
    <AppShell
      topBar={{
        breadcrumb: (
          <>
            <Link href="/queue" className="hover:text-warm-fog">Triage queue</Link>
            <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
            <span className="font-medium text-warm-fog">Clusters</span>
          </>
        ),
        right: (
          <Chip>
            {clusters.length} cluster{clusters.length === 1 ? "" : "s"}
          </Chip>
        ),
      }}
    >
      <div className="space-y-6">
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
      </div>
    </AppShell>
  );
}
