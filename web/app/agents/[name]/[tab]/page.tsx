import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import {
  getAgent,
  getAgentMetrics,
  getAgentPrompts,
  getAgentRuns,
  getAgentTools,
  getAgentWorklist,
  getAgentTimeseries,
  type AgentDetail,
  type AgentMetrics,
  type AgentPromptRow,
  type AgentRunsResponse,
  type AgentToolUsage,
  type TimeWindow,
  type WorklistItem,
  type MetricSeries,
} from "@/lib/api";
import { IdentityStrip } from "@/components/agent/identity-strip";
import { RunsTable } from "@/components/agent/runs-table";
import { VersionsTimeline } from "@/components/agent/versions-timeline";
import { ToolsTable } from "@/components/agent/tools-table";
import { ConfigForm } from "@/components/agent/config-form";
import { PromptsView } from "@/components/agent/prompts-view";
import { StackedBarChart } from "@/components/charts/bar-chart";
import { TimeRangePicker } from "@/components/agent/time-range-picker";
import { SharedCursorProvider } from "@/components/charts/shared-cursor";
import { TrendChart } from "@/components/charts/trend-chart";
import { AgentWorklist } from "@/components/agent/worklist";
import { ExportBar } from "@/components/agent/export-bar";

export const dynamic = "force-dynamic";

const TABS = ["overview", "runs", "prompt", "tools", "versions", "config"] as const;
type Tab = (typeof TABS)[number];

function parseWindow(v: string | undefined): TimeWindow {
  if (v === "24h" || v === "30d") return v;
  return "7d";
}

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

function PromptPlaceholder({ name }: { name: string }) {
  return (
    <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px] max-w-[760px]">
      <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
        follow-up · prompt tab
      </div>
      <div className="text-[13px] text-warm-fog mb-[4px]">
        The Prompt tab will show the system prompt for each version of{" "}
        <code className="font-mono text-aether-teal">{name}</code> and diff
        across versions.
      </div>
      <div className="text-[11px] text-patina leading-[1.5]">
        Lands once the SDK captures system prompts as a distinct resource
        attribute (not buried inside each LLM span&apos;s message history).
      </div>
    </div>
  );
}

function KpiTile({
  label,
  value,
  accent = false,
  warn = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
  warn?: boolean;
}) {
  const color = warn ? "text-warn" : accent ? "text-peach-neon" : "text-warm-fog";
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[6px]">
        {label}
      </div>
      <div className={`font-mono text-[20px] tracking-[-0.02em] ${color}`}>{value}</div>
    </div>
  );
}

function latencyTicks(m: AgentMetrics | null): number[] {
  const seriesMax = (m?.latency_series ?? []).reduce(
    (acc, p) => Math.max(acc, p.p99_latency_ms ?? 0),
    m?.p99_latency_ms ?? 0,
  );
  const rounded = Math.max(1000, Math.ceil((seriesMax || 1000) / 1000) * 1000);
  const step = rounded / 4;
  return [0, step, step * 2, step * 3, step * 4];
}

function latencyXLabels(m: AgentMetrics | null, window: TimeWindow): string[] {
  const series = m?.latency_series ?? [];
  if (series.length === 0) return ["start", "", "", "", "now"];
  const fmt = (iso: string) => {
    const d = new Date(iso);
    return window === "24h"
      ? `${String(d.getHours()).padStart(2, "0")}:00`
      : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  };
  return [
    fmt(series[0].bucket_start),
    "",
    fmt(series[Math.floor(series.length / 2)].bucket_start),
    "",
    fmt(series[series.length - 1].bucket_start),
  ];
}

const COST_PER_INPUT_TOKEN_USD = 0.000003;   // ~gpt-4o-mini input; placeholder
const COST_PER_OUTPUT_TOKEN_USD = 0.000012;  // ~gpt-4o-mini output; placeholder

function tokensCostFromRuns(
  runs: { started_at: string; input_tokens: number; output_tokens: number }[],
): { label: string; input_tokens: number; output_tokens: number; cost: number }[] {
  const buckets = new Map<string, { input: number; output: number }>();
  for (const r of runs) {
    const day = r.started_at.slice(0, 10);
    const b = buckets.get(day) ?? { input: 0, output: 0 };
    b.input += r.input_tokens ?? 0;
    b.output += r.output_tokens ?? 0;
    buckets.set(day, b);
  }
  return Array.from(buckets.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([day, { input, output }]) => {
      const label = new Date(day).toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
      const cost =
        input * COST_PER_INPUT_TOKEN_USD + output * COST_PER_OUTPUT_TOKEN_USD;
      return { label, input_tokens: input, output_tokens: output, cost };
    });
}

function seriesFor(series: MetricSeries[], metric: string): MetricSeries["buckets"] {
  return series.find((s) => s.metric === metric)?.buckets ?? [];
}

function SimpleVolume({
  runs,
  window,
}: {
  runs: { started_at: string; version_label: string | null }[];
  window: TimeWindow;
}) {
  const buckets = new Map<string, Map<string, number>>();
  const versions = new Set<string>();
  for (const r of runs) {
    const day = r.started_at.slice(0, 10);
    const ver = r.version_label ?? "—";
    versions.add(ver);
    const inner = buckets.get(day) ?? new Map<string, number>();
    inner.set(ver, (inner.get(ver) ?? 0) + 1);
    buckets.set(day, inner);
  }
  const versionOrder = Array.from(versions).slice(0, 6);
  const colors = ["#6BBAB1", "#E8A87C", "#7A8B8E", "#D98A6A", "#3A4950", "#2E3A40"];
  const bars = Array.from(buckets.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([day, vers]) => {
      const label = new Date(day).toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
      return {
        label,
        segments: versionOrder.map((v, i) => ({
          color: colors[i] ?? "#3A4950",
          value: vers.get(v) ?? 0,
        })),
      };
    });
  if (bars.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No data in {window}.</div>;
  }
  return <StackedBarChart bars={bars} />;
}

export default async function AgentTab({
  params,
  searchParams,
}: {
  params: Promise<{ name: string; tab: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { name, tab } = await params;
  if (!TABS.includes(tab as Tab)) notFound();
  const sp = await searchParams;
  const window = parseWindow(sp.window);

  let agent: AgentDetail;
  try {
    agent = await getAgent(name);
  } catch {
    notFound();
  }

  // Fetch only what each tab needs.
  let metrics: AgentMetrics | null = null;
  let tools: AgentToolUsage[] = [];
  let runs: AgentRunsResponse | null = null;
  let prompts: AgentPromptRow[] = [];
  let worklist: WorklistItem[] = [];
  let timeseries: MetricSeries[] = [];

  if (tab === "overview") {
    try {
      const [m, t, r, w, ts] = await Promise.all([
        getAgentMetrics(name, window),
        getAgentTools(name, window),
        getAgentRuns(name, { limit: 10 }),
        getAgentWorklist(name, window),
        getAgentTimeseries(name, window, [
          "p95_latency",
          "cost_per_1k",
          "tool_success",
          "feedback_down",
        ]),
      ]);
      metrics = m;
      tools = t;
      runs = r;
      worklist = w;
      timeseries = ts;
    } catch {
      // leave empties; page renders empty states
    }
  } else if (tab === "runs") {
    try {
      const [m, r] = await Promise.all([
        getAgentMetrics(name, window),
        getAgentRuns(name, { limit: 100 }),
      ]);
      metrics = m;
      runs = r;
    } catch {}
  } else if (tab === "tools") {
    try {
      const [m, t] = await Promise.all([
        getAgentMetrics(name, window),
        getAgentTools(name, window),
      ]);
      metrics = m;
      tools = t;
    } catch {}
  } else if (tab === "prompt") {
    try {
      const [m, p] = await Promise.all([
        getAgentMetrics(name, window),
        getAgentPrompts(name, 20),
      ]);
      metrics = m;
      prompts = p;
    } catch {}
  } else if (tab === "versions" || tab === "config") {
    try {
      metrics = await getAgentMetrics(name, window);
    } catch {}
  }

  const breadcrumb = (
    <>
      <Link href="/agents" className="hover:text-warm-fog">
        Agents
      </Link>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span className="font-medium text-warm-fog">{name}</span>
    </>
  );

  const latestVersion = agent.versions[0]?.label ?? null;
  const env = runs?.items[0]?.environment ?? null;
  const lastRunAt = runs?.items[0]?.started_at ?? null;

  const envList = Array.from(
    new Set((runs?.items ?? []).map((r) => r.environment).filter(Boolean)),
  ) as string[];

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Versions</CtxHeader>
      {agent.versions.length === 0 ? (
        <CtxItem>(none)</CtxItem>
      ) : (
        agent.versions.slice(0, 8).map((v, i) => (
          <CtxItem key={v.id} active={i === 0}>
            {v.label}
          </CtxItem>
        ))
      )}
      <CtxHeader>Environments</CtxHeader>
      {envList.length === 0 ? (
        <CtxItem>(none in window)</CtxItem>
      ) : (
        envList.slice(0, 8).map((e) => <CtxItem key={e}>{e}</CtxItem>)
      )}
      <CtxHeader>Saved filters</CtxHeader>
      <CtxItem>(Phase 4)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb,
        right: (
          <>
            <TimeRangePicker current={window} />
            <Chip>env: {env ?? "all"}</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <IdentityStrip
        agent={agent}
        version={latestVersion}
        env={env}
        metrics={metrics}
        lastRunAt={lastRunAt}
      />

      <div className="flex gap-[20px] border-b border-[color:var(--border)] -mx-[14px] px-[14px] mb-[14px]">
        {TABS.map((t) => {
          const active = t === tab;
          return (
            <Link
              key={t}
              href={`/agents/${encodeURIComponent(name)}/${t}`}
              className={`py-[10px] text-[12px] -mb-px border-b-2 ${
                active
                  ? "text-warm-fog border-b-aether-teal"
                  : "text-patina border-b-transparent hover:text-warm-fog"
              }`}
            >
              <span className="capitalize">{t}</span>
            </Link>
          );
        })}
      </div>

      {tab === "overview" ? (
        <>
          <div className="flex items-center justify-end mb-[10px]">
            <ExportBar agentName={name} window={window} />
          </div>

          <SharedCursorProvider>
            <div className="grid grid-cols-2 gap-[8px] mb-[10px]">
              <Card title={`p95 latency · ${window}`}>
                <TrendChart
                  metric="p95_latency"
                  buckets={seriesFor(timeseries, "p95_latency")}
                  format="latency_ms"
                  color="#6BBAB1"
                />
              </Card>
              <Card title={`cost / 1k runs · ${window}`}>
                <TrendChart
                  metric="cost_per_1k"
                  buckets={seriesFor(timeseries, "cost_per_1k")}
                  format="usd3"
                  color="#E8A87C"
                />
              </Card>
              <Card title={`tool success · ${window}`}>
                <TrendChart
                  metric="tool_success"
                  buckets={seriesFor(timeseries, "tool_success")}
                  format="pct1"
                  color="#A78BFA"
                />
              </Card>
              <Card title={`user 👎 · ${window}`}>
                <TrendChart
                  metric="feedback_down"
                  buckets={seriesFor(timeseries, "feedback_down")}
                  format="int"
                  color="#D98A6A"
                />
              </Card>
            </div>
          </SharedCursorProvider>

          <AgentWorklist agentName={name} items={worklist} />

          <div className="h-[10px]" />

          <Card title="Recent runs" className="!p-0">
            <RunsTable rows={runs?.items ?? []} />
          </Card>
        </>
      ) : tab === "runs" ? (
        <Card
          title={`All runs · ${window}`}
          right={
            runs
              ? `${runs.total.toLocaleString()} total · showing ${runs.items.length}`
              : undefined
          }
          className="!p-0"
        >
          <RunsTable rows={runs?.items ?? []} />
        </Card>
      ) : tab === "tools" ? (
        <Card
          title={`Tool usage · ${window}`}
          right={
            tools.length
              ? `${tools.length} tool${tools.length === 1 ? "" : "s"}`
              : undefined
          }
          className="!p-0"
        >
          <ToolsTable tools={tools} />
        </Card>
      ) : tab === "versions" ? (
        <Card
          title={`Versions · ${agent.versions.length}`}
          right="first-seen → last-seen"
          className="!p-0"
        >
          <VersionsTimeline versions={agent.versions} />
        </Card>
      ) : tab === "config" ? (
        <ConfigForm agent={agent} />
      ) : tab === "prompt" ? (
        <PromptsView prompts={prompts} />
      ) : (
        <PromptPlaceholder name={name} />
      )}
    </AppShell>
  );
}
