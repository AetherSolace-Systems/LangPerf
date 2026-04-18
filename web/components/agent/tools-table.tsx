import type { AgentToolUsage } from "@/lib/api";

export function ToolsTable({ tools }: { tools: AgentToolUsage[] }) {
  if (tools.length === 0) {
    return (
      <div className="text-patina text-[12px] p-[16px]">
        No tool calls captured for this agent in the selected window.
      </div>
    );
  }
  const max = Math.max(1, ...tools.map((t) => t.calls));
  const total = tools.reduce((s, t) => s + t.calls, 0);
  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        <tr>
          <Th>Tool</Th>
          <Th className="text-right">Calls</Th>
          <Th className="text-right">Share</Th>
          <Th>Distribution</Th>
          <Th className="text-right">Errors</Th>
          <Th className="text-right">Error rate</Th>
        </tr>
      </thead>
      <tbody>
        {tools.map((t) => {
          const pct = (t.calls / max) * 100;
          const share = total ? (t.calls / total) * 100 : 0;
          const errPct = t.calls ? (t.errors / t.calls) * 100 : 0;
          const warn = errPct > 2;
          return (
            <tr
              key={t.tool}
              className="border-b border-[color:var(--border)] last:border-b-0 hover:bg-[color:rgba(107,186,177,0.03)]"
            >
              <Td mono>{t.tool}</Td>
              <Td mono className="text-right">
                <b className="text-warm-fog">{t.calls.toLocaleString()}</b>
              </Td>
              <Td mono className="text-right">
                {share.toFixed(1)}%
              </Td>
              <Td>
                <div className="w-full h-[4px] bg-[color:rgba(122,139,142,0.15)] overflow-hidden">
                  <div
                    className="h-full"
                    style={{
                      width: `${pct}%`,
                      background: warn ? "#E8A87C" : "#6BBAB1",
                    }}
                  />
                </div>
              </Td>
              <Td mono className="text-right">
                {t.errors > 0 ? (
                  <span className="text-warn">{t.errors}</span>
                ) : (
                  <span className="text-patina">0</span>
                )}
              </Td>
              <Td mono className="text-right">
                {errPct > 0 ? (
                  <span className={warn ? "text-warn" : "text-patina"}>
                    {errPct.toFixed(1)}%
                  </span>
                ) : (
                  <span className="text-patina">—</span>
                )}
              </Td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`text-left font-mono text-[9px] text-patina uppercase tracking-[0.1em] px-[10px] py-[8px] border-b border-[color:var(--border)] font-medium ${className}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  mono = false,
  className = "",
}: {
  children: React.ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <td
      className={`px-[10px] py-[7px] text-warm-fog ${
        mono ? "font-mono text-[11px] text-patina" : ""
      } ${className}`}
    >
      {children}
    </td>
  );
}
