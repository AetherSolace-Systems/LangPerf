"use client";

import { useMemo } from "react";
import type { Span } from "@/lib/api";
import { DRIFT, kindSwatch } from "@/lib/colors";
import { fmtDuration } from "@/lib/format";
import { kindOf } from "@/lib/span-fields";
import { buildTree, type TreeNode } from "@/lib/tree";

type Row = {
  span: Span;
  kind: string;
  depth: number;
  startMs: number;
  endMs: number;
  leftPct: number;
  widthPct: number;
};

export function TrajectoryTimeline({
  spans,
  selectedId,
  onSelect,
}: {
  spans: Span[];
  selectedId: string | null;
  onSelect: (span: Span) => void;
}) {
  const { rows, totalMs, ticks, trajectoryStartMs } = useMemo(() => {
    if (spans.length === 0) {
      return { rows: [] as Row[], totalMs: 0, ticks: [] as number[], trajectoryStartMs: 0 };
    }

    const toMs = (iso: string) => new Date(iso).getTime();
    const allStart = Math.min(...spans.map((s) => toMs(s.started_at)));
    const allEnd = Math.max(
      ...spans.map((s) =>
        s.ended_at ? toMs(s.ended_at) : toMs(s.started_at) + (s.duration_ms ?? 0),
      ),
    );
    const total = Math.max(1, allEnd - allStart);

    const roots = buildTree(spans);
    const flat: Row[] = [];
    const walk = (n: TreeNode) => {
      const startMs = toMs(n.span.started_at);
      const endMs = n.span.ended_at
        ? toMs(n.span.ended_at)
        : startMs + (n.span.duration_ms ?? 0);
      const leftPct = ((startMs - allStart) / total) * 100;
      const widthPct = Math.max(0.4, ((endMs - startMs) / total) * 100);
      flat.push({
        span: n.span,
        kind: kindOf(n.span),
        depth: n.depth,
        startMs,
        endMs,
        leftPct,
        widthPct,
      });
      for (const c of n.children) walk(c);
    };
    for (const r of roots) walk(r);

    // Choose a sensible number of tick marks (4-6) based on duration.
    const tickCount = 5;
    const tickValues = Array.from({ length: tickCount + 1 }, (_, i) =>
      Math.round((total * i) / tickCount),
    );

    return {
      rows: flat,
      totalMs: total,
      ticks: tickValues,
      trajectoryStartMs: allStart,
    };
  }, [spans]);

  if (spans.length === 0) {
    return <div className="p-6 text-sm text-twilight">No spans to plot.</div>;
  }

  return (
    <div className="h-full flex flex-col font-mono text-xs">
      <TimeAxis ticks={ticks} totalMs={totalMs} />
      <div className="flex-1 overflow-y-auto">
        {rows.map((r) => (
          <TimelineRow
            key={r.span.span_id}
            row={r}
            selected={r.span.span_id === selectedId}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  );
}

const LABEL_WIDTH = 240;

function TimeAxis({ ticks, totalMs }: { ticks: number[]; totalMs: number }) {
  return (
    <div className="flex-shrink-0 flex border-b border-[color:var(--border)]">
      <div
        className="flex-shrink-0 px-3 py-1.5 text-[10px] text-twilight"
        style={{ width: LABEL_WIDTH }}
      >
        &nbsp;
      </div>
      <div className="relative flex-1 h-6">
        {ticks.map((t, i) => {
          const pct = (t / Math.max(1, totalMs)) * 100;
          return (
            <div
              key={i}
              className="absolute top-0 bottom-0 flex flex-col items-start"
              style={{
                left: `${pct}%`,
                transform: i === ticks.length - 1 ? "translateX(-100%)" : i === 0 ? "translateX(0)" : "translateX(-50%)",
              }}
            >
              <div className="w-px h-1.5 bg-[color:var(--border-strong)]" />
              <span className="text-[10px] text-twilight tabular-nums mt-0.5 px-0.5">
                {fmtTickLabel(t)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function fmtTickLabel(ms: number): string {
  if (ms === 0) return "0s";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)}s`;
  const mins = Math.floor(ms / 60_000);
  const secs = Math.round((ms % 60_000) / 1000);
  return secs ? `${mins}m${secs}s` : `${mins}m`;
}

function TimelineRow({
  row,
  selected,
  onSelect,
}: {
  row: Row;
  selected: boolean;
  onSelect: (span: Span) => void;
}) {
  const swatch = kindSwatch(row.kind);
  const isError = row.span.status_code === "ERROR";

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(row.span)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(row.span);
        }
      }}
      className={`flex border-b border-[color:var(--border)]/50 cursor-pointer hover:bg-linen/[0.03] ${
        selected ? "bg-drift-violet/10" : ""
      }`}
    >
      <div
        className="flex-shrink-0 flex items-center gap-2 px-3 py-1.5"
        style={{ width: LABEL_WIDTH, paddingLeft: `${row.depth * 12 + 12}px` }}
      >
        <span
          className="text-[10px] uppercase tracking-wider flex-shrink-0"
          style={{ color: swatch.fg, width: 50 }}
        >
          {row.kind}
        </span>
        <span className="flex-1 truncate text-linen">{row.span.name}</span>
      </div>
      <div className="relative flex-1 h-7">
        <div
          className="absolute top-1.5 bottom-1.5 rounded-sm transition-all"
          style={{
            left: `${row.leftPct}%`,
            width: `${row.widthPct}%`,
            background: swatch.bg,
            border: `1px solid ${selected ? DRIFT.marigold : swatch.border}`,
            boxShadow: selected ? `0 0 0 1px ${DRIFT.marigold}66` : undefined,
          }}
          title={`${row.span.name} · ${fmtDuration(row.span.duration_ms)}`}
        >
          <div
            className="absolute inset-y-0 left-0 w-0.5"
            style={{ background: swatch.solid }}
          />
        </div>
        {isError ? (
          <div
            className="absolute top-1.5 bottom-1.5 flex items-center pl-1"
            style={{ left: `${row.leftPct + row.widthPct}%` }}
          >
            <span className="text-coral">!</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
