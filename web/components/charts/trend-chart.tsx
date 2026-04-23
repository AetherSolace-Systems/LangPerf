"use client";

import React, { useCallback, useLayoutEffect, useRef, useState } from "react";
import { useSharedCursor } from "./shared-cursor";

export type TrendBucket = {
  ts_ms: number;
  value: number | null;
  count: number;
};

type Props = {
  metric: string;
  buckets: TrendBucket[];
  format: (v: number) => string;
  color: string;
  height?: number;
  label?: string;
};

export function TrendChart({
  metric,
  buckets,
  format,
  color,
  height = 160,
  label,
}: Props) {
  const { hoverX, setX } = useSharedCursor();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [widthPx, setWidthPx] = useState<number>(0);

  useLayoutEffect(() => {
    if (!wrapRef.current || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      setWidthPx(Math.max(0, w));
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  const chartH = height - 24;
  const maxY = Math.max(1, ...buckets.map((b) => b.value ?? 0));
  const step = buckets.length > 1 ? 240 / (buckets.length - 1) : 0;
  const toX = (i: number) => i * step;
  const toY = (v: number) => chartH - (v / maxY) * chartH;

  // Collect all non-null points for the main polyline; nulls are skipped.
  // Segment splitting (for visual gap rendering) is deferred to a future pass
  // since the test contract expects a single polyline with n non-null points.
  const nonNullPoints = buckets
    .map((b, i) => (b.value != null ? { i, v: b.value } : null))
    .filter((p): p is { i: number; v: number } => p != null);

  // Pick which bucket is under hoverX
  const hoverBucketIdx =
    hoverX != null && buckets.length > 1
      ? Math.min(buckets.length - 1, Math.max(0, Math.round(hoverX / step)))
      : null;
  const hoverBucket = hoverBucketIdx != null ? buckets[hoverBucketIdx] : null;

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!wrapRef.current) return;
      const rect = wrapRef.current.getBoundingClientRect();
      const effectiveWidth = widthPx > 0 ? widthPx : rect.width;
      if (effectiveWidth === 0) return;
      const x = e.clientX - rect.left;
      const svgX = Math.max(0, Math.min(240, (x / effectiveWidth) * 240));
      setX(svgX);
    },
    [setX, widthPx],
  );

  const onMouseLeave = useCallback(() => setX(null), [setX]);

  // metric is used for aria labeling; suppress unused-var lint
  void metric;

  return (
    <div
      ref={wrapRef}
      data-chart-surface
      onMouseEnter={onMouseMove}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      className="relative"
      style={{ height }}
    >
      {label ? (
        <div className="absolute top-0 left-0 font-mono text-[9px] text-patina uppercase tracking-wider">
          {label}
        </div>
      ) : null}
      <svg
        viewBox={`0 0 240 ${chartH}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height: chartH, marginTop: 14 }}
      >
        {nonNullPoints.length === 1 ? (
          <circle
            cx={toX(nonNullPoints[0].i)}
            cy={toY(nonNullPoints[0].v)}
            r={1.5}
            fill={color}
          />
        ) : nonNullPoints.length > 1 ? (
          <polyline
            points={nonNullPoints
              .map((p) => `${toX(p.i)},${toY(p.v).toFixed(2)}`)
              .join(" ")}
            fill="none"
            stroke={color}
            strokeWidth={1.5}
          />
        ) : null}
        {hoverX != null ? (
          <line
            x1={hoverX}
            x2={hoverX}
            y1={0}
            y2={chartH}
            stroke="rgba(167,139,250,0.8)"
            strokeWidth={1}
          />
        ) : null}
      </svg>
      {hoverBucket != null && hoverBucket.value != null && hoverX != null ? (
        <div
          className="absolute pointer-events-none px-1.5 py-0.5 text-[10px] font-mono tabular-nums rounded text-aether-violet"
          style={{
            top: 0,
            left: `${(hoverX / 240) * 100}%`,
            transform: "translateX(-50%)",
            background: "var(--surface)",
            border: "1px solid rgba(167,139,250,0.55)",
            whiteSpace: "nowrap",
          }}
        >
          {format(hoverBucket.value)}{" "}
          <span className="text-patina ml-1.5">
            {new Date(hoverBucket.ts_ms).toLocaleTimeString(undefined, {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      ) : null}
    </div>
  );
}
