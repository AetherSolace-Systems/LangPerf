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
  type AgentDetail,
  type AgentMetrics,
  type AgentPromptRow,
  type AgentRunsResponse,
  type AgentToolUsage,
  type TimeWindow,
} from "@/lib/api";
import { IdentityStrip } from "@/components/agent/identity-strip";
import { RunsTable } from "@/components/agent/runs-table";
import { VersionsTimeline } from "@/components/agent/versions-timeline";
import { ToolsTable } from "@/components/agent/tools-table";
import { ConfigForm } from "@/components/agent/config-form";
import { PromptsView } from "@/components/agent/prompts-view";
import { TopTools } from "@/components/dashboard/top-tools";
import { TokensCostChart } from "@/components/charts/tokens-cost-chart";
import { LineChart } from "@/components/charts/line-chart";
import { StackedBarChart } from "@/components/charts/bar-chart";
import { TimeRangePicker } from "@/components/agent/time-range-picker";

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

function flat(v: number | null): number[] {
  return v == null ? [] : [v, v, v, v, v, v, v];
}

function latencyTicks(m: AgentMetrics | null): number[] {
  const p99 = m?.p99_latency_ms ?? 1000;
  const rounded = Math.max(1000, Math.ceil(p99 / 1000) * 1000);
  const step = rounded / 4;
  return [0, step, step * 2, step * 3, step * 4];
}

function tokensCostFromRuns(
  runs: { started_at: string; token_count: number }[],
): { label: string; input_tokens: number; output_tokens: number; cost: number }[] {
  const buckets = new Map<string, number>();
  for (const r of runs) {
    const day = r.started_at.slice(0, 10);
    buckets.set(day, (buckets.get(day) ?? 0) + r.token_count);
  }
  return Array.from(buckets.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([day, total]) => {
      const label = new Date(day).toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
      const input_tokens = Math.round(total * 0.8);
      const output_tokens = total - input_tokens;
      const cost = total * 0.00001;
      return { label, input_tokens, output_tokens, cost };
    });
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

  if (tab === "overview") {
    try {
      const [m, t, r] = await Promise.all([
        getAgentMetrics(name, window),
        getAgentTools(name, window),
        getAgentRuns(name, { limit: 10 }),
      ]);
      metrics = m;
      tools = t;
      runs = r;
    } catch {
      // leave nulls; page renders empty states
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
          <div className="grid grid-cols-5 gap-[8px] mb-[10px]">
            <KpiTile
              label={`runs · ${window}`}
              value={metrics ? metrics.runs.toLocaleString() : "—"}
            />
            <KpiTile
              label="error rate"
              value={metrics ? `${(metrics.error_rate * 100).toFixed(1)}%` : "—"}
              accent={metrics != null && metrics.error_rate > 0}
              warn={metrics != null && metrics.error_rate > 0.05}
            />
            <KpiTile
              label="p95 latency"
              value={metrics?.p95_latency_ms != null ? `${metrics.p95_latency_ms}ms` : "—"}
            />
            <KpiTile label="tools called" value={String(tools.length)} />
            <KpiTile
              label="total tokens"
              value={metrics ? metrics.total_tokens.toLocaleString() : "—"}
            />
          </div>

          <div className="grid grid-cols-2 gap-[8px] mb-[10px]">
            <Card title={`Run volume · ${window}`}>
              <SimpleVolume runs={runs?.items ?? []} window={window} />
            </Card>
            <Card title={`Latency · p50/p95/p99 · ${window}`}>
              <LineChart
                lines={[
                  { name: "p50", color: "#E8A87C", values: flat(metrics?.p50_latency_ms ?? null) },
                  { name: "p95", color: "#6BBAB1", values: flat(metrics?.p95_latency_ms ?? null) },
                  { name: "p99", color: "#D98A6A", values: flat(metrics?.p99_latency_ms ?? null) },
                ]}
                xLabels={["start", "", "", "", "now"]}
                yTicks={latencyTicks(metrics)}
                yFormat={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`)}
              />
            </Card>
          </div>

          <div className="grid grid-cols-2 gap-[8px] mb-[10px]">
            <Card title={`Tokens & cost · ${window}`}>
              <TokensCostChart buckets={tokensCostFromRuns(runs?.items ?? [])} />
            </Card>
            <Card title={`Tools · ${window}`} right="defs →">
              <TopTools tools={tools} />
            </Card>
          </div>

          <Card title="Recent runs" className="!p-0">
            <RunsTable rows={runs?.items ?? []} />
          </Card>

          <div className="h-[10px]" />

          <div className="grid grid-cols-3 gap-[8px]">
            <V2Card
              label="Eval set · pass rate"
              body="Run a curated eval set against every new version. Gate prod promotion on pass rate."
            />
            <V2Card
              label="Comments & reviewers"
              body="SME notes on specific nodes. Assign flagged runs to reviewers."
            />
            <V2Card
              label="Replay against new prompt"
              body="Re-run a flagged trajectory against the next version to check if the issue was fixed."
            />
          </div>
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
