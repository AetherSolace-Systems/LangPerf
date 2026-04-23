import type { Span } from "@/lib/api";

export type Segment = {
  /** The `kind=trajectory` root span for this segment. */
  root: Span;
  /** Ms from the prior segment's `ended_at` to this segment's `started_at`. 0 for the first segment. */
  gapBeforeMs: number;
};

/**
 * Split a trajectory's spans into ordered durable-run segments.
 *
 * A segment is a root span (parent_span_id null) stamped with
 * `langperf.node.kind = "trajectory"`. Multiple such roots sharing one
 * trajectory id happen when the caller passes a stable `id=` to
 * `langperf.trajectory(...)` across process boundaries.
 *
 * Non-trajectory-kind orphan roots (rare) are intentionally excluded
 * from segment detection so they don't produce spurious "resumed after"
 * dividers in the UI.
 */
export function buildSegments(spans: Span[]): Segment[] {
  const roots = spans.filter(
    (s) =>
      s.parent_span_id == null &&
      (s.attributes as Record<string, unknown> | null)?.["langperf.node.kind"] ===
        "trajectory",
  );
  const ordered = [...roots].sort(
    (a, b) =>
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
  );
  return ordered.map((root, i) => {
    if (i === 0) return { root, gapBeforeMs: 0 };
    const prev = ordered[i - 1];
    const prevEnd = prev.ended_at
      ? new Date(prev.ended_at).getTime()
      : new Date(prev.started_at).getTime() + (prev.duration_ms ?? 0);
    const curStart = new Date(root.started_at).getTime();
    return { root, gapBeforeMs: Math.max(0, curStart - prevEnd) };
  });
}
