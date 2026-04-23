import React from "react";
import { describe, it, expect, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Span } from "@/lib/api";
import { TrajectoryTree } from "@/components/trajectory-tree";
import { SelectionProvider } from "@/components/selection-context";

afterEach(() => cleanup());

function makeSpan(overrides: Partial<Span> = {}): Span {
  return {
    span_id: "s",
    trace_id: "t",
    trajectory_id: "tr",
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

function renderTree(spans: Span[]) {
  return render(
    <SelectionProvider spans={spans}>
      <TrajectoryTree spans={spans} />
    </SelectionProvider>,
  );
}

describe("TrajectoryTree", () => {
  it("renders a single-segment tree identically (regression guard: no divider)", () => {
    renderTree([
      makeSpan({
        span_id: "r",
        name: "only-root",
        attributes: { "langperf.node.kind": "trajectory" },
      }),
    ]);
    expect(screen.getByText("only-root")).toBeTruthy();
    expect(screen.queryByText(/resumed after/i)).toBeNull();
  });

  it("renders a multi-segment divider labeled with the gap", () => {
    const seg1 = makeSpan({
      span_id: "r1",
      name: "seg-1",
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:05.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const seg2 = makeSpan({
      span_id: "r2",
      name: "seg-2",
      // 1 hour after seg-1 ended
      started_at: "2026-01-01T01:00:05.000Z",
      ended_at: "2026-01-01T01:00:06.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    renderTree([seg1, seg2]);
    expect(screen.getByText("seg-1")).toBeTruthy();
    expect(screen.getByText("seg-2")).toBeTruthy();
    // Exactly one divider between the two segments.
    const dividers = screen.queryAllByText(/resumed after/i);
    expect(dividers).toHaveLength(1);
    expect(dividers[0].textContent).toContain("1h");
  });

  it("renders dividers between N segments (one less than segment count)", () => {
    const mkRoot = (idx: number, startIso: string, endIso: string) =>
      makeSpan({
        span_id: `r${idx}`,
        name: `seg-${idx}`,
        started_at: startIso,
        ended_at: endIso,
        attributes: { "langperf.node.kind": "trajectory" },
      });
    renderTree([
      mkRoot(1, "2026-01-01T00:00:00.000Z", "2026-01-01T00:00:05.000Z"),
      mkRoot(2, "2026-01-01T00:10:00.000Z", "2026-01-01T00:10:05.000Z"),
      mkRoot(3, "2026-01-01T00:20:00.000Z", "2026-01-01T00:20:05.000Z"),
    ]);
    expect(screen.queryAllByText(/resumed after/i)).toHaveLength(2);
  });
});
