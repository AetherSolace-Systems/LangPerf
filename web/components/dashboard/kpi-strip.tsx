import type { OverviewKpi } from "@/lib/api";
import { fmtDuration } from "@/lib/format";

function Tile({ label, value, sub, accent = false, warn = false }: {
  label: string;
  value: string;
  sub?: string;
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
      {sub ? (
        <div className="font-mono text-[10px] text-patina mt-[3px]">{sub}</div>
      ) : null}
    </div>
  );
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function fmtLatency(ms: number | null): string {
  return ms == null ? "—" : fmtDuration(ms);
}

export function KpiStrip({ kpi, window }: { kpi: OverviewKpi; window: string }) {
  return (
    <div className="grid grid-cols-5 gap-[8px] mb-[10px]">
      <Tile label={`runs · ${window}`} value={kpi.runs.toLocaleString()} />
      <Tile label="agents" value={String(kpi.agents)} />
      <Tile
        label="error rate"
        value={fmtPct(kpi.error_rate)}
        warn={kpi.error_rate > 0.05}
        accent={kpi.error_rate > 0 && kpi.error_rate <= 0.05}
      />
      <Tile label="p95 latency" value={fmtLatency(kpi.p95_latency_ms)} />
      <Tile
        label="flagged"
        value={String(kpi.flagged)}
        accent={kpi.flagged > 0}
      />
    </div>
  );
}
