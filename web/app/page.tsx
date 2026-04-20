import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import {
  getOverview,
  listAgents,
  type AgentSummaryWithMetrics,
  type OverviewResponse,
  type TimeWindow,
} from "@/lib/api";
import { isRedirectError } from "@/lib/fetch-utils";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { AgentGrid } from "@/components/dashboard/agent-grid";
import { TopTools } from "@/components/dashboard/top-tools";
import { MostRanAgents } from "@/components/dashboard/most-ran-agents";
import { RecentFlagged } from "@/components/dashboard/recent-flagged";
import { StackedBarChart } from "@/components/charts/bar-chart";
import { LineChart } from "@/components/charts/line-chart";
import { TimeRangePicker } from "@/components/agent/time-range-picker";

export const dynamic = "force-dynamic";

function Card({
  title,
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[12px] ${className}`}>
      {title ? (
        <div className="flex items-center justify-between mb-[8px]">
          <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
            {title}
          </span>
          {right ? (
            <span className="font-mono text-[10px] text-aether-teal">{right}</span>
          ) : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}

function V2Card({ label, body }: { label: string; body: string }) {
  return (
    <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
        v2
      </div>
      <div className="text-[12px] text-warm-fog font-medium mb-[2px]">{label}</div>
      <div className="text-[11px] text-patina leading-[1.5]">{body}</div>
    </div>
  );
}

function parseWindow(v: string | undefined): TimeWindow {
  if (v === "24h" || v === "30d") return v;
  return "7d";
}

export default async function Dashboard({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const window = parseWindow(params.window);

  let overview: OverviewResponse;
  let agents: AgentSummaryWithMetrics[];
  try {
    const [ov, ag] = await Promise.all([
      getOverview(window),
      listAgents({ with_metrics: true, window }),
    ]);
    overview = ov;
    agents = ag as AgentSummaryWithMetrics[];
  } catch (err) {
    if (isRedirectError(err)) throw err;
    return (
      <AppShell
        topBar={{
          breadcrumb: <span className="font-medium text-warm-fog">Dashboard</span>,
        }}
      >
        <div
          className="rounded border p-4 text-sm"
          style={{
            borderColor: "rgba(217,138,106,0.45)",
            background: "rgba(217,138,106,0.1)",
          }}
        >
          <p className="font-medium text-warn">Could not reach langperf-api</p>
          <p className="mt-1 text-patina font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </AppShell>
    );
  }

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Pinned agents</CtxHeader>
      {agents.slice(0, 6).map((a) => (
        <CtxItem key={a.id} sub={a.metrics.runs.toLocaleString()}>
          <Link
            href={`/agents/${encodeURIComponent(a.name)}`}
            className="hover:underline"
          >
            {a.display_name ?? a.name}
          </Link>
        </CtxItem>
      ))}
      <CtxHeader>Saved views</CtxHeader>
      <CtxItem>(Phase 4)</CtxItem>
    </ContextSidebar>
  );

  // Volume bars — always last 24h in hourly buckets (24 bars). Label every 4
  // hours; blank label elsewhere to keep the axis readable.
  const volumeBars = overview.volume_by_day.map((d, i) => {
    const date = new Date(d.day);
    const hour = date.getHours();
    const label = i % 4 === 0 ? `${String(hour).padStart(2, "0")}:00` : "";
    return {
      label,
      segments: [
        { color: "#6BBAB1", value: d.prod },
        { color: "#E8A87C", value: d.staging },
        { color: "#7A8B8E", value: d.dev + d.other },
      ],
    };
  });

  const latencySeries = overview.latency_series ?? [];
  const latencyTicks = (() => {
    const maxFromSeries = latencySeries.reduce(
      (m, p) => Math.max(m, p.p99_latency_ms ?? 0),
      overview.kpi.p99_latency_ms ?? 0,
    );
    const rounded = Math.max(1000, Math.ceil((maxFromSeries || 1000) / 1000) * 1000);
    const step = rounded / 4;
    return [0, step, step * 2, step * 3, step * 4];
  })();
  const latencyXLabels = (() => {
    const len = latencySeries.length;
    if (len === 0) return ["start", "", "", "", "now"];
    const first = new Date(latencySeries[0].bucket_start);
    const last = new Date(latencySeries[len - 1].bucket_start);
    const fmt = (d: Date) =>
      window === "24h"
        ? `${String(d.getHours()).padStart(2, "0")}:00`
        : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    const mid = new Date(latencySeries[Math.floor(len / 2)].bucket_start);
    return [fmt(first), "", fmt(mid), "", fmt(last)];
  })();

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Dashboard</span>,
        right: (
          <>
            <TimeRangePicker current={window} />
            <Chip variant="primary">ingest ok</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <KpiStrip kpi={overview.kpi} window={window} />

      <div className="grid grid-cols-1 gap-[10px] mb-[10px]">
        <Card title="Run volume · last 24h · hourly · by env">
          <StackedBarChart bars={volumeBars} />
        </Card>
        <Card title={`Latency · p50/p95/p99 · ${window}`}>
          <LineChart
            lines={[
              { name: "p50", color: "#E8A87C", values: latencySeries.map((p) => p.p50_latency_ms) },
              { name: "p95", color: "#6BBAB1", values: latencySeries.map((p) => p.p95_latency_ms) },
              { name: "p99", color: "#D98A6A", values: latencySeries.map((p) => p.p99_latency_ms) },
            ]}
            xLabels={latencyXLabels}
            yTicks={latencyTicks}
            yFormat={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`)}
          />
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-[8px] mb-[10px]">
        <Card title={`Most ran agents · ${window}`}>
          <MostRanAgents agents={overview.most_ran_agents} />
        </Card>
        <Card title={`Top tools · ${window}`} right="across all agents">
          <TopTools tools={overview.top_tools} />
        </Card>
      </div>

      <Card title="Your agents">
        <AgentGrid agents={agents} />
      </Card>

      <div className="h-[10px]" />

      <Card title="Recent flagged" right={<Link href="/history">view history →</Link>}>
        <RecentFlagged rows={overview.recent_flagged} />
      </Card>

      <div className="h-[10px]" />

      <div className="grid grid-cols-3 gap-[8px]">
        <V2Card
          label="Triage queue"
          body="Priority-ordered runs needing review. Clustered failures across agents."
        />
        <V2Card
          label="Eval regressions"
          body="Which prompts/tools regressed against your eval set this week."
        />
        <V2Card
          label="Training data export"
          body="Flagged + corrected runs as SFT/DPO jsonl from this surface."
        />
      </div>
    </AppShell>
  );
}
