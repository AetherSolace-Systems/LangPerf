import React from "react";
import { describe, it, expect } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { SharedCursorProvider } from "@/components/charts/shared-cursor";
import { TrendChart } from "@/components/charts/trend-chart";

const BUCKETS = [
  { ts_ms: 1_000_000, value: 1, count: 1 },
  { ts_ms: 2_000_000, value: 3, count: 2 },
  { ts_ms: 3_000_000, value: 2, count: 1 },
];

describe("TrendChart", () => {
  it("renders a polyline with one point per non-null bucket", () => {
    const { container } = render(
      <SharedCursorProvider>
        <TrendChart
          metric="p95_latency"
          buckets={BUCKETS}
          format={(v) => `${v}ms`}
          color="#6BBAB1"
        />
      </SharedCursorProvider>,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    const points = polyline!.getAttribute("points")!.trim().split(/\s+/);
    expect(points).toHaveLength(3);
  });

  it("skips null values without rendering them", () => {
    const data = [
      { ts_ms: 1_000_000, value: 1, count: 1 },
      { ts_ms: 2_000_000, value: null, count: 0 },
      { ts_ms: 3_000_000, value: 3, count: 2 },
    ];
    const { container } = render(
      <SharedCursorProvider>
        <TrendChart metric="x" buckets={data} format={(v) => `${v}`} color="#fff" />
      </SharedCursorProvider>,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline!.getAttribute("points")!.trim().split(/\s+/)).toHaveLength(2);
  });

  it("renders data-chart-surface and polyline (hover interaction deferred to Playwright)", () => {
    const { container } = render(
      <SharedCursorProvider>
        <TrendChart
          metric="p95_latency"
          buckets={BUCKETS}
          format={(v) => `${v}ms`}
          color="#6BBAB1"
        />
      </SharedCursorProvider>,
    );
    const surface = container.querySelector("[data-chart-surface]");
    expect(surface).not.toBeNull();
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
  });
});
