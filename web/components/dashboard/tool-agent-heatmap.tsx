import { Fragment } from "react";
import type { HeatmapCell } from "@/lib/api";

export function ToolAgentHeatmap({ cells }: { cells: HeatmapCell[] }) {
  if (cells.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No data.</div>;
  }
  const agents = Array.from(new Set(cells.map((c) => c.agent_name)));
  const tools = Array.from(new Set(cells.map((c) => c.tool)));
  const map = new Map<string, number>();
  let max = 1;
  for (const c of cells) {
    map.set(`${c.agent_name}|${c.tool}`, c.calls);
    if (c.calls > max) max = c.calls;
  }
  const cellBg = (n: number | undefined): string => {
    if (n == null) return "rgba(122,139,142,0.08)";
    const alpha = Math.min(1, 0.18 + (n / max) * 0.8);
    return `rgba(107,186,177,${alpha.toFixed(2)})`;
  };
  const fmt = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  return (
    <div
      className="grid gap-[2px] text-[10px] font-mono"
      style={{ gridTemplateColumns: `140px repeat(${tools.length}, 1fr)` }}
    >
      <div />
      {tools.map((t) => (
        <div key={t} className="text-center text-patina truncate py-[4px]">
          {t.replace(/_/g, " ").slice(0, 10)}
        </div>
      ))}

      {agents.map((a) => (
        <Fragment key={a}>
          <div className="text-patina px-[6px] py-[4px] truncate">{a}</div>
          {tools.map((t) => {
            const n = map.get(`${a}|${t}`);
            return (
              <div
                key={`${a}-${t}`}
                className="h-[22px] flex items-center justify-center"
                style={{
                  background: cellBg(n),
                  color: n != null ? "#181D21" : "#7A8B8E",
                }}
              >
                {n != null ? fmt(n) : "—"}
              </div>
            );
          })}
        </Fragment>
      ))}
    </div>
  );
}
