import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import { listAgents, type AgentSummaryWithMetrics, type TimeWindow } from "@/lib/api";
import { AgentGrid } from "@/components/dashboard/agent-grid";
import { TimeRangePicker } from "@/components/agent/time-range-picker";

export const dynamic = "force-dynamic";

function parseWindow(v: string | undefined): TimeWindow {
  if (v === "24h" || v === "30d") return v;
  return "7d";
}

export default async function AgentsIndex({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const window = parseWindow(params.window);

  let agents: AgentSummaryWithMetrics[];
  try {
    agents = (await listAgents({ with_metrics: true, window })) as AgentSummaryWithMetrics[];
  } catch (err) {
    return (
      <AppShell
        topBar={{
          breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
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
      <CtxHeader action="+ new">Agents</CtxHeader>
      {agents.map((a) => (
        <CtxItem key={a.id} sub={a.metrics.runs.toLocaleString()}>
          <Link
            href={`/agents/${encodeURIComponent(a.name)}`}
            className="hover:underline"
          >
            {a.display_name ?? a.name}
          </Link>
        </CtxItem>
      ))}
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        right: (
          <>
            <TimeRangePicker current={window} />
            <Chip>env: all</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <AgentGrid agents={agents} />
    </AppShell>
  );
}
