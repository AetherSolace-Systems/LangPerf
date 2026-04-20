import { describe, it, expect } from "vitest";
import type { Span } from "@/lib/api";
import { buildEdges } from "@/lib/graph-edges";

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

/** Helper: sibling spans under a shared parent, sequential by default. */
function seq(span_id: string, atSec: number, lenMs: number, attrs: Record<string, unknown> = {}, name = span_id): Span {
  const start = new Date(1735689600000 + atSec * 1000).toISOString(); // 2025-01-01
  const end = new Date(1735689600000 + atSec * 1000 + lenMs).toISOString();
  return makeSpan({
    span_id,
    parent_span_id: "root",
    name,
    started_at: start,
    ended_at: end,
    duration_ms: lenMs,
    attributes: attrs,
  });
}

describe("buildEdges", () => {
  it("returns no edges for empty input", () => {
    expect(buildEdges([])).toEqual([]);
  });

  it("connects two sequential siblings with a 'next' edge", () => {
    const a = seq("a", 0, 100);
    const b = seq("b", 10, 100);
    const edges = buildEdges([a, b]);
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe("a");
    expect(edges[0].target).toBe("b");
    expect(edges[0].data?.label).toBe("next");
  });

  it("creates a fan-out/fan-in diamond when the middle pair overlaps", () => {
    // a (0..1), b (2..8), c (3..7), d (10..11)
    // b and c overlap → single parallel group between a and d.
    const a = seq("a", 0, 1000);
    const b = seq("b", 2, 6000);
    const c = seq("c", 3, 4000);
    const d = seq("d", 10, 1000);
    const edges = buildEdges([a, b, c, d]);
    const pairs = edges.map((e) => `${e.source}->${e.target}`).sort();
    expect(pairs).toEqual(["a->b", "a->c", "b->d", "c->d"]);
  });

  it("labels llm→tool as tool:<name> using tool.name attr", () => {
    const llm = seq("llm1", 0, 100, { "openinference.span.kind": "llm" });
    const tool = seq("tool1", 5, 100, {
      "openinference.span.kind": "tool",
      "tool.name": "search_docs",
    });
    const edges = buildEdges([llm, tool]);
    expect(edges).toHaveLength(1);
    expect(edges[0].data?.label).toBe("tool:search_docs");
  });

  it("labels tool→llm as 'return'", () => {
    const tool = seq("t", 0, 100, { "openinference.span.kind": "tool" });
    const llm = seq("l", 5, 100, { "openinference.span.kind": "llm" });
    const edges = buildEdges([tool, llm]);
    expect(edges[0].data?.label).toBe("return");
  });

  it("labels llm→llm as 'message'", () => {
    const l1 = seq("l1", 0, 100, { "openinference.span.kind": "llm" });
    const l2 = seq("l2", 5, 100, { "openinference.span.kind": "llm" });
    const edges = buildEdges([l1, l2]);
    expect(edges[0].data?.label).toBe("message");
  });

  it("labels any→agent as delegate:<agent.name>", () => {
    const caller = seq("c", 0, 100, { "openinference.span.kind": "llm" });
    const agent = seq("a", 5, 100, { "openinference.span.kind": "agent" }, "SubPlanner");
    const edges = buildEdges([caller, agent]);
    expect(edges[0].data?.label).toBe("delegate:SubPlanner");
  });

  it("labels agent→next as 'resume ← <shortname>' when the exit leaf differs from the agent", () => {
    // Root has two siblings: an agent frame "Planner" with a child leaf
    // "finalize", and a following LLM "l".
    const agent = seq("agent", 0, 500, { "openinference.span.kind": "agent" }, "Planner");
    const leaf = makeSpan({
      span_id: "leaf",
      parent_span_id: "agent",
      name: "finalize",
      started_at: new Date(1735689600000 + 100).toISOString(),
      ended_at: new Date(1735689600000 + 400).toISOString(),
      duration_ms: 300,
      attributes: { "openinference.span.kind": "tool" },
    });
    const after = seq("after", 1, 100, { "openinference.span.kind": "llm" });
    const edges = buildEdges([agent, leaf, after]);
    // The edge at the root-children layer is agent→after
    const rootEdge = edges.find((e) => e.source === "agent" && e.target === "after");
    expect(rootEdge).toBeDefined();
    expect(rootEdge!.data?.label).toBe("resume ← finalize");
  });
});
