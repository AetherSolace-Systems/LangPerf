import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import { ContextSidebar, CtxHeader, CtxItem } from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";

export const dynamic = "force-dynamic";

function KpiTile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[6px]">
        {label}
      </div>
      <div className="font-mono text-[20px] text-warm-fog tracking-[-0.02em]">{value}</div>
      {sub ? (
        <div className="font-mono text-[10px] text-patina mt-[3px]">{sub}</div>
      ) : null}
    </div>
  );
}

export default function Dashboard() {
  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Pinned agents</CtxHeader>
      <CtxItem>(lands in Phase 2)</CtxItem>
      <CtxHeader>Saved views</CtxHeader>
      <CtxItem>(lands in Phase 2)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Dashboard</span>,
        right: <Chip variant="primary">ingest ok</Chip>,
      }}
      contextSidebar={sidebar}
    >
      <div className="grid grid-cols-5 gap-[8px] mb-[10px]">
        <KpiTile label="runs · 7d" value="—" sub="wait for Phase 2" />
        <KpiTile label="agents" value="—" sub="wait for Phase 2" />
        <KpiTile label="error rate" value="—" />
        <KpiTile label="p95 latency" value="—" />
        <KpiTile label="flagged" value="—" />
      </div>

      <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
        <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
          phase 1 · the shell is ready
        </div>
        <div className="text-[13px] text-warm-fog mb-[4px]">
          Charts, agent grid, top tools, heatmap, and flagged runs arrive in Phase 2
          (first-class Agent data model).
        </div>
        <div className="text-[11px] text-patina leading-[1.5]">
          Meanwhile the existing trajectory list is available at{" "}
          <Link href="/history" className="text-aether-teal hover:underline">
            /history
          </Link>
          . OTLP ingestion at{" "}
          <code className="font-mono text-aether-teal">POST /v1/traces</code> is unchanged.
        </div>
      </div>
    </AppShell>
  );
}
