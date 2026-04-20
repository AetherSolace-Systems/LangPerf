import { describe, it, expect } from "vitest";
import type { Span } from "@/lib/api";
import { endMs, groupByParallel, PARALLEL_TOLERANCE_MS } from "@/lib/span-timing";

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

describe("endMs", () => {
  it("returns ended_at epoch ms when ended_at is set", () => {
    const s = makeSpan({
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:02.500Z",
      duration_ms: 9999, // ignored when ended_at present
    });
    expect(endMs(s)).toBe(new Date("2026-01-01T00:00:02.500Z").getTime());
  });

  it("computes from started_at + duration_ms when ended_at is null", () => {
    const s = makeSpan({
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: null,
      duration_ms: 1500,
    });
    expect(endMs(s)).toBe(new Date("2026-01-01T00:00:00.000Z").getTime() + 1500);
  });

  it("treats null duration_ms as 0 when ended_at is null", () => {
    const s = makeSpan({
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: null,
      duration_ms: null,
    });
    expect(endMs(s)).toBe(new Date("2026-01-01T00:00:00.000Z").getTime());
  });
});

describe("groupByParallel", () => {
  type Item = { start: number; end: number; id: string };
  const getStart = (t: Item) => t.start;
  const getEnd = (t: Item) => t.end;

  it("returns [] on empty input", () => {
    expect(groupByParallel<Item>([], getStart, getEnd)).toEqual([]);
  });

  it("groups a single item into one group", () => {
    const a = { start: 0, end: 100, id: "a" };
    expect(groupByParallel([a], getStart, getEnd)).toEqual([[a]]);
  });

  it("returns two groups for two sequential items", () => {
    const a = { start: 0, end: 100, id: "a" };
    const b = { start: 500, end: 700, id: "b" };
    expect(groupByParallel([a, b], getStart, getEnd)).toEqual([[a], [b]]);
  });

  it("returns one group for two clearly overlapping items", () => {
    const a = { start: 0, end: 1000, id: "a" };
    const b = { start: 500, end: 1500, id: "b" };
    expect(groupByParallel([a, b], getStart, getEnd)).toEqual([[a, b]]);
  });

  it("applies PARALLEL_TOLERANCE_MS slop — a tiny overlap is still sequential", () => {
    const slop = PARALLEL_TOLERANCE_MS;
    const a = { start: 0, end: 1000, id: "a" };
    // b starts 30ms before a ends → overlap = 30ms < 60ms tolerance → sequential
    const b = { start: 1000 - Math.floor(slop / 2), end: 2000, id: "b" };
    expect(groupByParallel([a, b], getStart, getEnd)).toEqual([[a], [b]]);
  });

  it("treats three items as [[a,b],[c]] when only the first two overlap", () => {
    const a = { start: 0, end: 1000, id: "a" };
    const b = { start: 500, end: 1500, id: "b" };
    const c = { start: 3000, end: 4000, id: "c" };
    expect(groupByParallel([a, b, c], getStart, getEnd)).toEqual([[a, b], [c]]);
  });

  it("widens currentEnd to include later-finishing members of the same group", () => {
    // b starts inside a, then c starts inside b's extended end.
    const a = { start: 0, end: 1000, id: "a" };
    const b = { start: 500, end: 3000, id: "b" };
    const c = { start: 2000, end: 4000, id: "c" };
    expect(groupByParallel([a, b, c], getStart, getEnd)).toEqual([[a, b, c]]);
  });
});
