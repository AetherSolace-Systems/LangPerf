"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { TrajectoryDetail } from "@/lib/api";
import { fmtDuration, fmtTime } from "@/lib/format";
import { NodeDetailPanel } from "@/components/node-detail-panel";
import { TrajectoryTree } from "@/components/trajectory-tree";

export function TrajectoryView({ trajectory }: { trajectory: TrajectoryDetail }) {
  const firstSpanId = trajectory.spans[0]?.span_id ?? null;
  const [selectedId, setSelectedId] = useState<string | null>(firstSpanId);

  const selectedSpan = useMemo(
    () =>
      selectedId
        ? trajectory.spans.find((s) => s.span_id === selectedId) ?? null
        : null,
    [selectedId, trajectory.spans],
  );

  return (
    <div className="h-screen flex flex-col">
      <header className="border-b border-[var(--border)] px-6 py-3 flex-shrink-0">
        <Link
          href="/"
          className="text-xs text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          ← all trajectories
        </Link>
        <div className="mt-1 flex items-baseline gap-3 flex-wrap">
          <h1 className="text-base font-semibold tracking-tight">
            {trajectory.name ?? (
              <em className="text-[var(--muted)] font-normal">(unnamed)</em>
            )}
          </h1>
          <span className="text-xs font-mono text-[var(--muted)]">
            {trajectory.id.slice(0, 8)}…
          </span>
          <span className="text-xs text-[var(--muted)]">·</span>
          <span className="text-xs text-[var(--muted)]">
            {trajectory.service_name}
            {trajectory.environment ? ` · ${trajectory.environment}` : ""}
          </span>
          <span className="text-xs text-[var(--muted)]">·</span>
          <span className="text-xs text-[var(--muted)] tabular-nums">
            {trajectory.step_count} step{trajectory.step_count === 1 ? "" : "s"}
          </span>
          <span className="text-xs text-[var(--muted)]">·</span>
          <span className="text-xs text-[var(--muted)] tabular-nums">
            {trajectory.token_count.toLocaleString()}t
          </span>
          <span className="text-xs text-[var(--muted)]">·</span>
          <span className="text-xs text-[var(--muted)] tabular-nums">
            {fmtDuration(trajectory.duration_ms)}
          </span>
          <span className="text-xs text-[var(--muted)]">·</span>
          <span className="text-xs text-[var(--muted)]">
            {fmtTime(trajectory.started_at)}
          </span>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 min-w-0 overflow-y-auto border-r border-[var(--border)]">
          <TrajectoryTree
            spans={trajectory.spans}
            selectedId={selectedId}
            onSelect={(s) => setSelectedId(s.span_id)}
          />
        </div>
        <div className="w-[480px] flex-shrink-0 overflow-hidden">
          <NodeDetailPanel span={selectedSpan} />
        </div>
      </div>
    </div>
  );
}
