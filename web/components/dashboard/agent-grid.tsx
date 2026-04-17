import Link from "next/link";
import type { AgentSummaryWithMetrics } from "@/lib/api";
import { Sparkline } from "@/components/charts/sparkline";
import { fmtDuration } from "@/lib/format";

function statusDot(errorRate: number): string {
  if (errorRate === 0) return "#6BBAB1";
  if (errorRate < 0.05) return "#E8A87C";
  return "#D98A6A";
}

export function AgentGrid({ agents }: { agents: AgentSummaryWithMetrics[] }) {
  if (agents.length === 0) {
    return <div className="text-patina text-[12px] py-[24px]">No agents yet.</div>;
  }
  return (
    <div className="grid grid-cols-4 gap-[8px]">
      {agents.map((a) => {
        const errPct = (a.metrics.error_rate * 100).toFixed(1);
        const dot = statusDot(a.metrics.error_rate);
        return (
          <Link
            key={a.id}
            href={`/agents/${encodeURIComponent(a.name)}`}
            className="block border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[10px] hover:border-[color:var(--border-strong)]"
          >
            <div className="flex items-center gap-[6px] text-[12px] font-medium">
              <span style={{ background: dot, width: 6, height: 6, display: "inline-block" }} />
              <span className="truncate">{a.display_name ?? a.name}</span>
              <span className="ml-auto font-mono text-[9px] text-patina">
                v{a.version_count || 0}
              </span>
            </div>
            <div className="font-mono text-[10px] text-patina mt-[2px]">
              {a.metrics.runs.toLocaleString()} · {errPct}% err · p95{" "}
              {a.metrics.p95_latency_ms != null
                ? fmtDuration(a.metrics.p95_latency_ms)
                : "—"}
            </div>
            <Sparkline values={a.sparkline} stroke={dot} />
          </Link>
        );
      })}
    </div>
  );
}
