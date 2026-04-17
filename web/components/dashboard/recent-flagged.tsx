import Link from "next/link";
import type { FlaggedRun } from "@/lib/api";
import { ClientTime } from "@/components/client-time";

function tagCls(tag: string | null): string {
  if (tag === "bad") return "text-warn border-[color:rgba(217,138,106,0.4)]";
  if (tag === "interesting" || tag === "todo")
    return "text-peach-neon border-[color:rgba(232,168,124,0.4)]";
  if (tag === "good") return "text-aether-teal border-[color:rgba(107,186,177,0.35)]";
  return "text-patina border-[color:var(--border-strong)]";
}

export function RecentFlagged({ rows }: { rows: FlaggedRun[] }) {
  if (rows.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No flagged runs in range.</div>;
  }
  return (
    <div>
      {rows.map((r) => (
        <Link
          key={r.id}
          href={`/r/${r.id}`}
          className="grid grid-cols-[60px_1fr_70px_80px] gap-[10px] items-center py-[6px] border-b border-[color:var(--border)] last:border-b-0 text-[12px] hover:bg-[color:rgba(107,186,177,0.03)]"
        >
          <span className="font-mono text-[10px] text-patina">{r.id.slice(0, 6)}</span>
          <span className="truncate">
            {r.agent_name ? (
              <span className="text-warm-fog">{r.agent_name}</span>
            ) : null}
            {r.summary ? (
              <span className="text-patina"> · {r.summary}</span>
            ) : null}
          </span>
          <span
            className={`font-mono text-[9px] uppercase tracking-[0.08em] border px-[6px] py-[2px] text-center ${tagCls(r.status_tag)}`}
          >
            {r.status_tag ?? "—"}
          </span>
          <span className="font-mono text-[10px] text-patina text-right">
            <ClientTime iso={r.started_at} />
          </span>
        </Link>
      ))}
    </div>
  );
}
