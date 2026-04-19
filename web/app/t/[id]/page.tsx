import Link from "next/link";
import { notFound } from "next/navigation";
import { getTrajectory } from "@/lib/api";
import { fetchTrajectoryHits } from "@/lib/triage";
import { listRewrites } from "@/lib/rewrites";
import { TrajectoryView } from "@/components/trajectory-view";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar } from "@/components/shell/context-sidebar";
import { HeuristicHitsPanel } from "@/components/queue/heuristic-hits-panel";
import { RewriteList } from "@/components/rewrite/rewrite-list";
import { Chip } from "@/components/ui/chip";

export const dynamic = "force-dynamic";

export default async function TrajectoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let traj;
  try {
    traj = await getTrajectory(id);
  } catch (err) {
    if (err instanceof Error && err.message.includes("404")) notFound();
    throw err;
  }
  let hits: import("@/lib/triage").HeuristicHit[] = [];
  try {
    hits = await fetchTrajectoryHits(id);
  } catch {
    // hits are best-effort; don't crash the page if triage API is absent
  }
  let rewrites: import("@/lib/rewrites").Rewrite[] = [];
  try {
    rewrites = await listRewrites(id);
  } catch {
    // rewrites are best-effort; don't crash the page if the endpoint is absent
  }

  const serviceLabel = traj.service_name;
  const envLabel = traj.environment ?? "—";

  const breadcrumb = (
    <>
      <Link href="/history" className="hover:text-warm-fog">History</Link>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span className="font-mono text-[11px] text-warm-fog">{id.slice(0, 8)}</span>
    </>
  );

  const sidebar = hits.length > 0 ? (
    <ContextSidebar>
      <HeuristicHitsPanel hits={hits} />
    </ContextSidebar>
  ) : undefined;

  return (
    <AppShell
      topBar={{
        breadcrumb,
        right: <Chip>env: {envLabel}</Chip>,
      }}
      contextSidebar={sidebar}
    >
      {/* Identity strip — Phase 1 fills it from service_name/environment since
          Agents aren't first-class yet. Phase 2 swaps to real agent+version. */}
      <div className="flex items-center gap-2 px-[14px] py-[9px] -mx-[14px] -mt-[14px] mb-[14px] border-b border-[color:var(--border)] bg-gradient-to-b from-[color:var(--surface-2)] to-[color:var(--background)]">
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mr-[2px]">Service</span>
        <Chip>{serviceLabel}</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Env</span>
        <Chip>{envLabel}</Chip>
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mx-[2px] ml-[6px]">Run</span>
        <Chip>{id.slice(0, 8)}</Chip>
        <div className="flex-1" />
        <span className="font-mono text-[10px] text-patina">
          {traj.step_count} steps · {traj.token_count.toLocaleString()}t
        </span>
      </div>

      <TrajectoryView trajectory={traj} />

      <section className="mt-8 space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-aether-teal">
          Rewrites
        </h2>
        <RewriteList rewrites={rewrites} />
      </section>
    </AppShell>
  );
}
