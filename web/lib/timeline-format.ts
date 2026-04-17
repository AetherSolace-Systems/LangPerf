/**
 * Time-axis helpers for the trajectory timeline.
 *
 * Extracted from `trajectory-timeline.tsx` so the component focuses on
 * rendering + state and the formatting/tick-math lives in one place. All
 * functions below are deterministic but timezone-dependent (they call
 * `new Date(absMs).getHours()` etc.) — callers must gate them behind a
 * `mounted` client flag when SSR-rendered, the same way ClientTime does.
 */

/** Choose a tick interval that targets ~`targetPx` spacing and walk the trajectory. */
export function buildTicks(
  totalMs: number,
  pxPerMs: number,
  targetPx: number = 110,
): { tickIntervalMs: number; ticks: number[] } {
  if (totalMs <= 0) return { tickIntervalMs: 1000, ticks: [0] };
  const desiredMs = targetPx / Math.max(0.0001, pxPerMs);
  const candidates = [
    1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10_000, 15_000,
    30_000, 60_000, 120_000, 300_000, 600_000,
  ];
  const interval =
    candidates.find((c) => c >= desiredMs) ?? candidates[candidates.length - 1];
  const count = Math.max(1, Math.ceil(totalMs / interval));
  const ticks: number[] = [];
  for (let i = 0; i <= count; i++) {
    const t = i * interval;
    if (t <= totalMs) ticks.push(t);
  }
  if (ticks[ticks.length - 1] !== totalMs) ticks.push(totalMs);
  return { tickIntervalMs: interval, ticks };
}

/** HH:MM:SS (optionally .SSS). User's local TZ. Render client-side only. */
export function fmtWallTime(
  absMs: number,
  { ms = false }: { ms?: boolean } = {},
): string {
  const d = new Date(absMs);
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  const s = String(d.getSeconds()).padStart(2, "0");
  if (!ms) return `${h}:${m}:${s}`;
  const millis = String(d.getMilliseconds()).padStart(3, "0");
  return `${h}:${m}:${s}.${millis}`;
}

/** Format a tick label. Resolution follows the tick interval: ≥1s → HH:MM:SS,
 *  ≥100ms → :SS.S, ≥10ms → :SS.SS, else :SS.SSS. */
export function fmtTickTime(absMs: number, tickIntervalMs: number): string {
  if (tickIntervalMs >= 1000) return fmtWallTime(absMs);
  const d = new Date(absMs);
  const s = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  if (tickIntervalMs >= 100) return `:${s}.${ms.slice(0, 1)}`;
  if (tickIntervalMs >= 10) return `:${s}.${ms.slice(0, 2)}`;
  return `:${s}.${ms}`;
}

export function fmtDate(absMs: number): string {
  return new Date(absMs).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

/** Human-readable description of the timeline's current pixel/ms zoom. */
export function fmtScale(pxPerMs: number): string {
  if (pxPerMs >= 1) return `${pxPerMs.toFixed(pxPerMs >= 10 ? 0 : 1)}px/ms`;
  const pxPerSec = pxPerMs * 1000;
  if (pxPerSec >= 1) return `${pxPerSec.toFixed(pxPerSec >= 10 ? 0 : 1)}px/s`;
  const pxPerMin = pxPerSec * 60;
  return `${pxPerMin.toFixed(pxPerMin >= 10 ? 0 : 1)}px/min`;
}
