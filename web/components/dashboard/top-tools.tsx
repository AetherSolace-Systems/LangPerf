import type { TopTool } from "@/lib/api";

export function TopTools({ tools }: { tools: TopTool[] }) {
  const max = Math.max(1, ...tools.map((t) => t.calls));
  if (tools.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No tool calls in range.</div>;
  }
  return (
    <div>
      {tools.map((t) => {
        const pct = (t.calls / max) * 100;
        const errPct = t.calls ? (t.errors / t.calls) * 100 : 0;
        const warn = errPct > 2;
        return (
          <div
            key={t.tool}
            className="flex items-center py-[5px] text-[12px] border-b border-[color:var(--border)] last:border-b-0"
          >
            <span className="font-mono flex-1 truncate">{t.tool}</span>
            <div className="w-[100px] h-[4px] bg-[color:rgba(122,139,142,0.15)] mx-[10px] overflow-hidden">
              <div
                className="h-full"
                style={{
                  width: `${pct}%`,
                  background: warn ? "#E8A87C" : "#6BBAB1",
                }}
              />
            </div>
            <span className="font-mono text-[10px] text-patina min-w-[74px] text-right tabular-nums">
              {t.calls.toLocaleString()}
              {t.errors > 0 ? (
                <span className="text-warn ml-[4px]">{errPct.toFixed(1)}%e</span>
              ) : null}
            </span>
          </div>
        );
      })}
    </div>
  );
}
