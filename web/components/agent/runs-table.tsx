import Link from "next/link";
import type { AgentRunRow } from "@/lib/api";
import { fmtDuration } from "@/lib/format";
import { ClientTime } from "@/components/client-time";

function tagCls(tag: string | null): string {
  if (tag === "bad") return "text-warn border-[color:rgba(217,138,106,0.4)]";
  if (tag === "interesting" || tag === "todo")
    return "text-peach-neon border-[color:rgba(232,168,124,0.4)]";
  if (tag === "good") return "text-aether-teal border-[color:rgba(107,186,177,0.35)]";
  return "text-patina border-[color:var(--border-strong)]";
}

export function RunsTable({
  rows,
  showAgent = false,
}: {
  rows: AgentRunRow[];
  showAgent?: boolean;
}) {
  if (rows.length === 0) {
    return <div className="text-patina text-[12px] p-[16px]">No runs.</div>;
  }
  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        <tr>
          <Th>Time</Th>
          <Th>ID</Th>
          {showAgent ? <Th>Agent</Th> : null}
          <Th>Input</Th>
          <Th className="text-right">Steps</Th>
          <Th className="text-right">Tokens</Th>
          <Th className="text-right">Latency</Th>
          <Th>Ver</Th>
          <Th>Env</Th>
          <Th>Status</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr
            key={r.id}
            className="border-b border-[color:var(--border)] last:border-b-0 hover:bg-[color:rgba(107,186,177,0.03)]"
          >
            <Td mono>
              <ClientTime iso={r.started_at} />
            </Td>
            <Td mono>
              <Link href={`/r/${r.id}`} className="text-aether-teal hover:underline">
                {r.id.slice(0, 6)}
              </Link>
            </Td>
            {showAgent ? (
              <Td>
                {r.agent_name ? (
                  <Link
                    href={`/agents/${encodeURIComponent(r.agent_name)}`}
                    className="text-aether-teal hover:underline"
                  >
                    {r.agent_name}
                  </Link>
                ) : (
                  <span className="text-patina">—</span>
                )}
              </Td>
            ) : null}
            <Td>
              <span className="truncate inline-block max-w-[360px] align-bottom">
                {r.name ?? <em className="text-patina">(unnamed)</em>}
              </span>
            </Td>
            <Td mono className="text-right">
              <b className="text-warm-fog">{r.step_count}</b>
            </Td>
            <Td mono className="text-right">
              <b className="text-warm-fog">{r.token_count.toLocaleString()}</b>
            </Td>
            <Td mono className="text-right">
              <b className="text-warm-fog">
                {r.duration_ms != null ? fmtDuration(r.duration_ms) : "—"}
              </b>
            </Td>
            <Td mono>{r.version_label ?? "—"}</Td>
            <Td mono>{r.environment ?? "—"}</Td>
            <Td>
              <span
                className={`inline-block font-mono text-[9px] uppercase tracking-[0.08em] border px-[6px] py-[2px] ${tagCls(r.status_tag)}`}
              >
                {r.status_tag ?? "—"}
              </span>
            </Td>
          </tr>
        ))}
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
      className={`px-[10px] py-[7px] text-warm-fog ${mono ? "font-mono text-[11px] text-patina" : ""} ${className}`}
    >
      {children}
    </td>
  );
}
