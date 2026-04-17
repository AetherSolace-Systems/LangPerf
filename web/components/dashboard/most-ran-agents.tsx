import Link from "next/link";
import type { MostRanAgent } from "@/lib/api";

export function MostRanAgents({ agents }: { agents: MostRanAgent[] }) {
  const max = Math.max(1, ...agents.map((a) => a.runs));
  if (agents.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No agent runs in range.</div>;
  }
  return (
    <div>
      {agents.map((a) => {
        const pct = (a.runs / max) * 100;
        const errPct = a.error_rate * 100;
        const warn = errPct > 5;
        return (
          <Link
            key={a.name}
            href={`/agents/${encodeURIComponent(a.name)}`}
            className="flex items-center py-[5px] text-[12px] border-b border-[color:var(--border)] last:border-b-0 hover:bg-[color:rgba(107,186,177,0.03)]"
          >
            <span className="flex-1 truncate text-warm-fog">{a.name}</span>
            <div className="w-[100px] h-[4px] bg-[color:rgba(122,139,142,0.15)] mx-[10px] overflow-hidden">
              <div
                className="h-full"
                style={{ width: `${pct}%`, background: warn ? "#E8A87C" : "#6BBAB1" }}
              />
            </div>
            <span className="font-mono text-[10px] text-patina min-w-[74px] text-right tabular-nums">
              {a.runs.toLocaleString()}
              {errPct > 0 ? (
                <span className="text-warn ml-[4px]">{errPct.toFixed(1)}%e</span>
              ) : null}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
