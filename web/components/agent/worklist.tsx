"use client";

import Link from "next/link";
import type { WorklistItem } from "@/lib/api";

const URGENCY_COLOR: Record<WorklistItem["urgency"], string> = {
  high: "text-warn border-warn",
  med: "text-peach-neon border-peach-neon",
  low: "text-patina border-[color:var(--border)]",
};

export function AgentWorklist({
  agentName,
  items,
}: {
  agentName: string;
  items: WorklistItem[];
}) {
  if (items.length === 0) {
    return (
      <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[18px] text-center">
        <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[6px]">
          worklist
        </div>
        <div className="text-[12px] text-patina">
          Nothing ranked high enough to surface. Come back as data accumulates.
        </div>
      </div>
    );
  }
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)]">
      <div className="flex items-center justify-between px-[12px] py-[8px] border-b border-[color:var(--border)]">
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
          worklist · top {items.length}
        </span>
      </div>
      <ul>
        {items.map((it, i) => (
          <li
            key={`${it.signal}-${i}`}
            className="grid grid-cols-[28px_1fr_auto_auto] gap-[10px] items-center px-[12px] py-[10px] border-b border-[color:var(--border)]/50 last:border-b-0 hover:bg-warm-fog/[0.03]"
          >
            <span className="font-mono text-[10px] text-patina text-right">
              {i + 1}
            </span>
            <div className="min-w-0">
              <RowLink agentName={agentName} item={it} />
              <div className="text-[10px] text-patina truncate">
                {it.subtitle}
              </div>
            </div>
            <span
              className={`font-mono text-[9px] uppercase tracking-wider border rounded px-[6px] py-[1px] ${URGENCY_COLOR[it.urgency]}`}
            >
              {it.urgency}
            </span>
            <span className="font-mono text-[9px] text-patina tabular-nums">
              {it.affected_runs} runs
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RowLink({ agentName, item }: { agentName: string; item: WorklistItem }) {
  const target = deriveTarget(agentName, item);
  if (target == null) {
    return (
      <span className="text-[12px] text-warm-fog truncate block">
        {item.title}
      </span>
    );
  }
  return (
    <Link
      href={target}
      className="text-[12px] text-warm-fog hover:text-aether-teal truncate block"
    >
      {item.title}
    </Link>
  );
}

/**
 * Map a worklist item's signal to a pre-filterable destination page.
 * Aggregate deltas (cost / latency / completion-drop) stay informational in
 * this phase — they don't have a matching pre-filterable URL today.
 */
function deriveTarget(agentName: string, item: WorklistItem): string | null {
  if (item.signal.startsWith("heuristic:")) {
    const kind = item.signal.slice("heuristic:".length);
    return `/history?agent=${encodeURIComponent(agentName)}&heuristic=${kind}`;
  }
  if (item.signal === "feedback:thumbs_down") {
    return `/history?agent=${encodeURIComponent(agentName)}&feedback=down`;
  }
  return null;
}
