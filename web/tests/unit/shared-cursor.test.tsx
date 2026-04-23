import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, fireEvent, screen, cleanup } from "@testing-library/react";
import { SharedCursorProvider, useSharedCursor } from "@/components/charts/shared-cursor";

function Reader() {
  const { hoverX } = useSharedCursor();
  return <div data-testid="read">{hoverX === null ? "null" : String(hoverX)}</div>;
}

function Writer() {
  const { setX } = useSharedCursor();
  return (
    <button data-testid="write" onClick={() => setX(42)}>
      set
    </button>
  );
}

describe("SharedCursorProvider", () => {
  afterEach(() => cleanup());

  it("starts with hoverX null", () => {
    render(
      <SharedCursorProvider>
        <Reader />
      </SharedCursorProvider>,
    );
    expect(screen.getByTestId("read").textContent).toBe("null");
  });

  it("sibling setX updates hoverX seen by Reader", () => {
    render(
      <SharedCursorProvider>
        <Reader />
        <Writer />
      </SharedCursorProvider>,
    );
    fireEvent.click(screen.getByTestId("write"));
    expect(screen.getByTestId("read").textContent).toBe("42");
  });

  it("useSharedCursor outside provider throws", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Reader />)).toThrow(/SharedCursorProvider/);
    spy.mockRestore();
  });
});
