"use client";

import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Span } from "@/lib/api";
import { DRIFT, kindSwatch } from "@/lib/colors";
import { fmtDuration } from "@/lib/format";
import { kindOf } from "@/lib/span-fields";
import {
  buildTicks,
  fmtDate,
  fmtScale,
  fmtTickTime,
  fmtWallTime,
} from "@/lib/timeline-format";
import { buildTree, type TreeNode } from "@/lib/tree";

type Row = {
  span: Span;
  kind: string;
  depth: number;
  startMs: number; // absolute wall-clock ms
  endMs: number; // absolute wall-clock ms
  offsetMs: number; // ms from trajectory start
  durationMs: number;
};

const LABEL_WIDTH = 240;
const DEFAULT_PX_PER_MS_MIN = 0.01;
const DEFAULT_PX_PER_MS_MAX = 1000;

export function TrajectoryTimeline({
  spans,
  selectedId,
  onSelect,
}: {
  spans: Span[];
  selectedId: string | null;
  onSelect: (span: Span) => void;
}) {
  const { rows, trajectoryStartMs, trajectoryEndMs, totalMs } = useMemo(() => {
    if (spans.length === 0) {
      return {
        rows: [] as Row[],
        trajectoryStartMs: 0,
        trajectoryEndMs: 0,
        totalMs: 0,
      };
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
      flat.push({
        span: n.span,
        kind: kindOf(n.span),
        depth: n.depth,
        startMs,
        endMs,
        offsetMs: startMs - allStart,
        durationMs: Math.max(0, endMs - startMs),
      });
      for (const c of n.children) walk(c);
    };
    for (const r of roots) walk(r);

    return {
      rows: flat,
      trajectoryStartMs: allStart,
      trajectoryEndMs: allEnd,
      totalMs: total,
    };
  }, [spans]);

  // Scroll container → we measure its width to drive "fit" zoom.
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [containerWidth, setContainerWidth] = useState<number>(800);
  const [pxPerMs, setPxPerMs] = useState<number | null>(null);

  // Hydration-safe flag: any wall-clock text renders empty on the server + first
  // client render (so SSR and hydration match), then flips true after mount to
  // reveal the user's local timezone. Same pattern ClientTime uses elsewhere.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // Observe scroll container size so "fit" works after layout.
  useLayoutEffect(() => {
    if (!scrollRef.current) return;
    const measure = () => {
      if (!scrollRef.current) return;
      const w = Math.max(
        300,
        scrollRef.current.clientWidth - LABEL_WIDTH - 24,
      );
      setContainerWidth(w);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(scrollRef.current);
    return () => ro.disconnect();
  }, []);

  // Default to fit-width when totalMs or container first becomes known.
  useEffect(() => {
    if (totalMs > 0 && pxPerMs === null) {
      setPxPerMs(containerWidth / totalMs);
    }
  }, [totalMs, containerWidth, pxPerMs]);

  const effectivePxPerMs = pxPerMs ?? Math.max(1, containerWidth / Math.max(1, totalMs));
  const trackWidth = Math.max(containerWidth, totalMs * effectivePxPerMs);

  const { tickIntervalMs, ticks } = useMemo(
    () => buildTicks(totalMs, effectivePxPerMs),
    [totalMs, effectivePxPerMs],
  );

  if (spans.length === 0) {
    return <div className="p-6 text-sm text-twilight">No spans to plot.</div>;
  }

  const zoomIn = () =>
    setPxPerMs((p) =>
      Math.min(
        DEFAULT_PX_PER_MS_MAX,
        (p ?? containerWidth / Math.max(1, totalMs)) * 1.6,
      ),
    );
  const zoomOut = () =>
    setPxPerMs((p) =>
      Math.max(
        DEFAULT_PX_PER_MS_MIN,
        (p ?? containerWidth / Math.max(1, totalMs)) / 1.6,
      ),
    );
  const fit = () => setPxPerMs(containerWidth / Math.max(1, totalMs));

  return (
    <div className="relative h-full">
      <ZoomControls
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
        onFit={fit}
        pxPerMs={effectivePxPerMs}
      />
      <div className="absolute top-2 left-4 z-30 text-[10px] font-mono text-twilight pointer-events-none">
        <span className="text-linen/80">
          {mounted ? fmtDate(trajectoryStartMs) : ""}
        </span>
        <span className="ml-2">
          {mounted
            ? `${fmtWallTime(trajectoryStartMs, { ms: true })} → ${fmtWallTime(
                trajectoryEndMs,
                { ms: true },
              )}`
            : ""}
        </span>
        <span className="ml-2">({fmtDuration(totalMs)})</span>
      </div>

      <div
        ref={scrollRef}
        className="h-full overflow-auto font-mono text-xs"
      >
        {/* Axis row — sticky to top so it stays visible while scrolling rows. */}
        <div
          className="flex sticky top-0 z-20 bg-midnight border-b border-[color:var(--border)]"
          style={{ minWidth: LABEL_WIDTH + trackWidth }}
        >
          <div
            className="flex-shrink-0 sticky left-0 z-10 bg-midnight"
            style={{ width: LABEL_WIDTH, height: 32 }}
          />
          <div
            className="relative"
            style={{ width: trackWidth, height: 32 }}
          >
            {ticks.map((tickMs, i) => {
              const leftPx = tickMs * effectivePxPerMs;
              const absMs = trajectoryStartMs + tickMs;
              const anchor =
                i === 0
                  ? "translateX(0)"
                  : i === ticks.length - 1
                    ? "translateX(-100%)"
                    : "translateX(-50%)";
              return (
                <div
                  key={i}
                  className="absolute top-0 bottom-0 flex flex-col items-start"
                  style={{ left: leftPx, transform: anchor }}
                >
                  <div className="w-px h-2 bg-[color:var(--border-strong)]" />
                  <span className="text-[10px] text-twilight tabular-nums mt-0.5 px-1 whitespace-nowrap">
                    {mounted ? fmtTickTime(absMs, tickIntervalMs) : ""}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Rows */}
        <div style={{ minWidth: LABEL_WIDTH + trackWidth }}>
          {rows.map((r) => (
            <TimelineRow
              key={r.span.span_id}
              row={r}
              selected={r.span.span_id === selectedId}
              onSelect={onSelect}
              pxPerMs={effectivePxPerMs}
              trackWidth={trackWidth}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function ZoomControls({
  onZoomIn,
  onZoomOut,
  onFit,
  pxPerMs,
}: {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  pxPerMs: number;
}) {
  return (
    <div className="absolute top-1.5 right-3 z-30 flex items-center gap-1 bg-deep-indigo/80 backdrop-blur border border-[color:var(--border)] rounded px-1.5 py-0.5">
      <button
        type="button"
        onClick={onZoomOut}
        className="px-1.5 text-linen/80 hover:text-marigold text-sm leading-none"
        aria-label="zoom out"
      >
        −
      </button>
      <button
        type="button"
        onClick={onFit}
        className="px-1.5 text-[10px] text-twilight hover:text-linen uppercase tracking-wider"
      >
        fit
      </button>
      <button
        type="button"
        onClick={onZoomIn}
        className="px-1.5 text-linen/80 hover:text-marigold text-sm leading-none"
        aria-label="zoom in"
      >
        +
      </button>
      <span className="text-[9px] text-twilight tabular-nums ml-1 border-l border-[color:var(--border)] pl-1.5">
        {fmtScale(pxPerMs)}
      </span>
    </div>
  );
}

function TimelineRow({
  row,
  selected,
  onSelect,
  pxPerMs,
  trackWidth,
}: {
  row: Row;
  selected: boolean;
  onSelect: (span: Span) => void;
  pxPerMs: number;
  trackWidth: number;
}) {
  const swatch = kindSwatch(row.kind);
  const isError = row.span.status_code === "ERROR";
  const leftPx = row.offsetMs * pxPerMs;
  const widthPx = Math.max(3, row.durationMs * pxPerMs);

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
        className="flex-shrink-0 sticky left-0 z-10 bg-midnight flex items-center gap-2 px-3 py-1.5"
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
      <div
        className="relative h-7 flex-shrink-0"
        style={{ width: trackWidth }}
      >
        <div
          className="absolute top-1.5 bottom-1.5 rounded-sm transition-all"
          style={{
            left: leftPx,
            width: widthPx,
            background: swatch.bg,
            border: `1px solid ${selected ? DRIFT.marigold : swatch.border}`,
            boxShadow: selected ? `0 0 0 1px ${DRIFT.marigold}66` : undefined,
          }}
          title={`${row.span.name} · ${fmtDuration(row.durationMs)}`}
        >
          <div
            className="absolute inset-y-0 left-0 w-0.5"
            style={{ background: swatch.solid }}
          />
        </div>
        {isError ? (
          <div
            className="absolute top-1.5 bottom-1.5 flex items-center pl-1"
            style={{ left: leftPx + widthPx }}
          >
            <span className="text-coral">!</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}

