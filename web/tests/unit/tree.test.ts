import { describe, it, expect } from "vitest";
import type { Span } from "@/lib/api";
import { buildTree } from "@/lib/tree";

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

describe("buildTree", () => {
  it("returns [] for no spans", () => {
    expect(buildTree([])).toEqual([]);
  });

  it("returns a single root with no children for one span", () => {
    const root = makeSpan({ span_id: "root" });
    const tree = buildTree([root]);
    expect(tree).toHaveLength(1);
    expect(tree[0].span.span_id).toBe("root");
    expect(tree[0].children).toEqual([]);
    expect(tree[0].depth).toBe(0);
  });

  it("builds parent → children relationships", () => {
    const root = makeSpan({ span_id: "root", started_at: "2026-01-01T00:00:00.000Z" });
    const c1 = makeSpan({
      span_id: "c1",
      parent_span_id: "root",
      started_at: "2026-01-01T00:00:00.100Z",
    });
    const c2 = makeSpan({
      span_id: "c2",
      parent_span_id: "root",
      started_at: "2026-01-01T00:00:00.200Z",
    });
    const tree = buildTree([c2, root, c1]); // intentionally out of order
    expect(tree).toHaveLength(1);
    expect(tree[0].span.span_id).toBe("root");
    expect(tree[0].children.map((c) => c.span.span_id)).toEqual(["c1", "c2"]);
    expect(tree[0].children.every((c) => c.depth === 1)).toBe(true);
  });

  it("sorts siblings by started_at ascending", () => {
    const root = makeSpan({ span_id: "root", started_at: "2026-01-01T00:00:00.000Z" });
    const later = makeSpan({
      span_id: "later",
      parent_span_id: "root",
      started_at: "2026-01-01T00:00:05.000Z",
    });
    const earlier = makeSpan({
      span_id: "earlier",
      parent_span_id: "root",
      started_at: "2026-01-01T00:00:01.000Z",
    });
    const tree = buildTree([root, later, earlier]);
    expect(tree[0].children.map((c) => c.span.span_id)).toEqual([
      "earlier",
      "later",
    ]);
  });

  it("treats spans whose parent_span_id is unknown as roots (orphan survives)", () => {
    // parent "missing" does not exist in the span list — current behavior
    // is to drop the parent lookup and treat the span as a root.
    const orphan = makeSpan({
      span_id: "orphan",
      parent_span_id: "missing",
      started_at: "2026-01-01T00:00:00.000Z",
    });
    const actualRoot = makeSpan({
      span_id: "root",
      parent_span_id: null,
      started_at: "2026-01-01T00:00:01.000Z",
    });
    const tree = buildTree([orphan, actualRoot]);
    const rootIds = tree.map((r) => r.span.span_id).sort();
    expect(rootIds).toEqual(["orphan", "root"]);
    expect(tree.every((r) => r.depth === 0)).toBe(true);
  });

  it("assigns correct nested depths", () => {
    const root = makeSpan({ span_id: "root" });
    const mid = makeSpan({
      span_id: "mid",
      parent_span_id: "root",
      started_at: "2026-01-01T00:00:00.100Z",
    });
    const leaf = makeSpan({
      span_id: "leaf",
      parent_span_id: "mid",
      started_at: "2026-01-01T00:00:00.200Z",
    });
    const tree = buildTree([root, mid, leaf]);
    expect(tree[0].depth).toBe(0);
    expect(tree[0].children[0].depth).toBe(1);
    expect(tree[0].children[0].children[0].depth).toBe(2);
  });
});
