import { Chip } from "@/components/ui/chip";
import { fmtDuration } from "@/lib/format";
import { ClientTime } from "@/components/client-time";
import type { AgentDetail, AgentMetrics } from "@/lib/api";

export function IdentityStrip({
  agent,
  version,
  env,
  metrics,
  lastRunAt,
}: {
  agent: AgentDetail;
  version: string | null;
  env: string | null;
  metrics: AgentMetrics | null;
  lastRunAt: string | null;
}) {
  return (
    <div className="flex items-center gap-2 px-[14px] py-[9px] -mx-[14px] -mt-[14px] mb-[14px] border-b border-[color:var(--border)] bg-gradient-to-b from-[color:var(--surface-2)] to-[color:var(--background)]">
      <Label>Agent</Label>
      <Chip>{agent.display_name ?? agent.name}</Chip>
      <Label className="ml-[6px]">Ver</Label>
      <Chip>{version ?? "—"}</Chip>
      <Label className="ml-[6px]">Env</Label>
      <Chip>{env ?? "—"}</Chip>
      <div className="flex-1" />
      <span className="font-mono text-[10px] text-patina">
        {lastRunAt ? (
          <>
            last run <b className="text-warm-fog font-medium"><ClientTime iso={lastRunAt} /></b> ·{" "}
          </>
        ) : null}
        {metrics ? (
          <>
            <b className="text-warm-fog font-medium">{metrics.runs.toLocaleString()}</b>/{metrics.window} ·{" "}
            {metrics.p50_latency_ms != null ? (
              <>p50 <b className="text-warm-fog font-medium">{fmtDuration(metrics.p50_latency_ms)}</b> · </>
            ) : null}
            {metrics.p95_latency_ms != null ? (
              <>p95 <b className="text-warm-fog font-medium">{fmtDuration(metrics.p95_latency_ms)}</b> · </>
            ) : null}
            err <b className="text-warn font-medium">{(metrics.error_rate * 100).toFixed(1)}%</b>
          </>
        ) : null}
      </span>
    </div>
  );
}

function Label({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={`font-mono text-[9px] text-patina uppercase tracking-[0.1em] mr-[2px] ${className}`}
    >
      {children}
    </span>
  );
}
