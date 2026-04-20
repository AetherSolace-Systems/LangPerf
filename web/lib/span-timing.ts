import type { Span } from "./api";

// Keep in sync across all graph layout/edge modules.
export const PARALLEL_TOLERANCE_MS = 60;

export function endMs(s: Span): number {
  if (s.ended_at) return new Date(s.ended_at).getTime();
  return new Date(s.started_at).getTime() + (s.duration_ms ?? 0);
}

/**
 * Bucket consecutive items that overlap in time. Input MUST be pre-sorted
 * by start time. Adjacent items whose time ranges overlap (within
 * PARALLEL_TOLERANCE_MS slop) land in the same group.
 */
export function groupByParallel<T>(
  items: T[],
  getStart: (t: T) => number,
  getEnd: (t: T) => number,
): T[][] {
  if (items.length === 0) return [];
  const groups: T[][] = [];
  let current: T[] = [items[0]];
  let currentEnd = getEnd(items[0]);
  for (let i = 1; i < items.length; i++) {
    const it = items[i];
    const startMs = getStart(it);
    if (startMs < currentEnd - PARALLEL_TOLERANCE_MS) {
      current.push(it);
      currentEnd = Math.max(currentEnd, getEnd(it));
    } else {
      groups.push(current);
      current = [it];
      currentEnd = getEnd(it);
    }
  }
  groups.push(current);
  return groups;
}
