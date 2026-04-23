import { describe, it, expect } from "vitest";
import type { Span } from "@/lib/api";
import { buildSegments } from "@/lib/segments";

function makeSpan(overrides: Partial<Span> = {}): Span {
  return {
    span_id: "s1",
    trace_id: "t1",
    trajectory_id: "tr1",
    parent_span_id: null,
    name: "test",
    kind: null,
    started_at: "2026-01-01T00:00:00.000Z",
    ended_at: "2026-01-01T00:00:01.000Z",
    duration_ms: 1000,
    attributes: {},
    events: null,
    status_code: null,
    notes: null,
    ...overrides,
  };
}

describe("buildSegments", () => {
  it("returns [] for no spans", () => {
    expect(buildSegments([])).toEqual([]);
  });

  it("returns one segment for a single-root trajectory", () => {
    const root = makeSpan({
      span_id: "r",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const segs = buildSegments([root]);
    expect(segs).toHaveLength(1);
    expect(segs[0].root.span_id).toBe("r");
    expect(segs[0].gapBeforeMs).toBe(0);
  });

  it("identifies multiple kind=trajectory roots as distinct segments", () => {
    const r1 = makeSpan({
      span_id: "r1",
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:05.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const r2 = makeSpan({
      span_id: "r2",
      started_at: "2026-01-01T00:10:00.000Z",
      ended_at: "2026-01-01T00:10:02.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const segs = buildSegments([r2, r1]); // out of order
    expect(segs.map((s) => s.root.span_id)).toEqual(["r1", "r2"]);
    // Gap is 10:00:00 - 00:00:05 = 9m55s → 595_000 ms.
    expect(segs[1].gapBeforeMs).toBe(595_000);
    expect(segs[0].gapBeforeMs).toBe(0);
  });

  it("ignores non-trajectory-kind roots when computing segments", () => {
    // An orphan non-trajectory root should not be treated as a segment.
    const trajectoryRoot = makeSpan({
      span_id: "r",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const orphan = makeSpan({
      span_id: "o",
      parent_span_id: null,
      attributes: { "langperf.node.kind": "tool" },
    });
    const segs = buildSegments([trajectoryRoot, orphan]);
    expect(segs).toHaveLength(1);
    expect(segs[0].root.span_id).toBe("r");
  });

  it("sorts segments by started_at ascending", () => {
    const later = makeSpan({
      span_id: "b",
      started_at: "2026-01-01T01:00:00.000Z",
      ended_at: "2026-01-01T01:00:01.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const earlier = makeSpan({
      span_id: "a",
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:01.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const segs = buildSegments([later, earlier]);
    expect(segs.map((s) => s.root.span_id)).toEqual(["a", "b"]);
  });
});
