import { describe, it, expect } from "vitest";
import { fmtDurationHuman } from "@/lib/format";

describe("fmtDurationHuman", () => {
  it("sub-second → ms", () => {
    expect(fmtDurationHuman(250)).toBe("250ms");
  });

  it("sub-minute → seconds", () => {
    expect(fmtDurationHuman(1500)).toBe("2s");
    expect(fmtDurationHuman(45_000)).toBe("45s");
  });

  it("sub-hour → minutes", () => {
    expect(fmtDurationHuman(60_000)).toBe("1m");
    expect(fmtDurationHuman(30 * 60_000)).toBe("30m");
  });

  it("sub-day → hours", () => {
    expect(fmtDurationHuman(60 * 60_000)).toBe("1h");
    expect(fmtDurationHuman(5 * 60 * 60_000)).toBe("5h");
  });

  it("days", () => {
    expect(fmtDurationHuman(24 * 60 * 60_000)).toBe("1d");
    expect(fmtDurationHuman(3 * 24 * 60 * 60_000)).toBe("3d");
  });
});
