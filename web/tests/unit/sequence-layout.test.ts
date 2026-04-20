import { describe, it, expect } from "vitest";
import type { Span } from "@/lib/api";
import { buildSequenceLayout } from "@/lib/sequence-layout";

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

const STEP_HEIGHT = 58;
const EXPANDED_STEP_HEIGHT = 300;

function child(span_id: string, parent: string, atSec: number, lenMs: number, attrs: Record<string, unknown> = {}): Span {
  const base = Date.UTC(2026, 0, 1);
  return makeSpan({
    span_id,
    parent_span_id: parent,
    name: span_id,
    started_at: new Date(base + atSec * 1000).toISOString(),
    ended_at: new Date(base + atSec * 1000 + lenMs).toISOString(),
    duration_ms: lenMs,
    attributes: attrs,
  });
}

describe("buildSequenceLayout", () => {
  it("returns an empty shape for empty input", () => {
    expect(buildSequenceLayout([])).toEqual({
      all: [],
      rootIds: [],
      maxExecOrder: 0,
    });
  });

  it("builds a single step node for a lone leaf span", () => {
    const leaf = makeSpan({ span_id: "leaf", parent_span_id: null });
    const out = buildSequenceLayout([leaf]);
    expect(out.all).toHaveLength(1);
    expect(out.all[0].kind).toBe("step");
    expect(out.all[0].id).toBe("leaf");
    expect(out.all[0].execOrder).toBe(1);
    expect(out.rootIds).toEqual(["leaf"]);
    expect(out.maxExecOrder).toBe(1);
  });

  it("wraps two sequential leaves under an agent frame with execOrders 1,2", () => {
    const agent = makeSpan({
      span_id: "agent",
      parent_span_id: null,
      attributes: { "openinference.span.kind": "agent" },
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:05.000Z",
      duration_ms: 5000,
    });
    // Sequential: l1 fully before l2 (gap > tolerance).
    const l1 = child("l1", "agent", 0, 500);
    const l2 = child("l2", "agent", 2, 500);
    const { all, rootIds, maxExecOrder } = buildSequenceLayout([agent, l1, l2]);

    expect(rootIds).toEqual(["agent"]);
    const agentNode = all.find((n) => n.id === "agent");
    expect(agentNode?.kind).toBe("frame");
    expect(agentNode?.frameKind).toBe("agent");

    const leafNodes = all.filter((n) => n.kind === "step");
    expect(leafNodes.map((n) => n.id)).toEqual(["l1", "l2"]);
    expect(leafNodes.map((n) => n.execOrder)).toEqual([1, 2]);
    expect(leafNodes.every((n) => n.parentId === "agent")).toBe(true);
    expect(maxExecOrder).toBe(2);
  });

  it("inserts a synthetic parallel frame when two child leaves overlap in time", () => {
    const agent = makeSpan({
      span_id: "agent",
      parent_span_id: null,
      attributes: { "openinference.span.kind": "agent" },
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:05.000Z",
      duration_ms: 5000,
    });
    // Overlapping: l1 [0..2000], l2 [500..2500]
    const l1 = child("l1", "agent", 0, 2000);
    const l2 = child("l2", "agent", 0.5, 2000);
    const { all } = buildSequenceLayout([agent, l1, l2]);

    const parallelFrame = all.find((n) => n.frameKind === "parallel");
    expect(parallelFrame).toBeDefined();
    expect(parallelFrame?.parentId).toBe("agent");
    expect(parallelFrame?.kind).toBe("frame");
    expect(parallelFrame?.span).toBeNull();
    // Both leaves should be nested under the parallel frame.
    const leafNodes = all.filter((n) => n.kind === "step");
    expect(leafNodes.every((n) => n.parentId === parallelFrame!.id)).toBe(true);
  });

  it("uses EXPANDED_STEP_HEIGHT for leaf steps when expandAll=true", () => {
    const leaf = makeSpan({ span_id: "only", parent_span_id: null });
    const compact = buildSequenceLayout([leaf]);
    expect(compact.all[0].height).toBe(STEP_HEIGHT);

    const expanded = buildSequenceLayout([leaf], { expandAll: true });
    expect(expanded.all[0].height).toBe(EXPANDED_STEP_HEIGHT);
  });
});
