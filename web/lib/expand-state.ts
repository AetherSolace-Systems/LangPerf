"use client";

import { useFullscreen } from "@/components/graph/fullscreen-context";

/**
 * Returns [expanded, toggle] for a given span.
 *
 * Precedence:
 *  - If global `expandAll` is on → expanded is true.
 *  - Else per-span override in `expandedIds`.
 */
export function useExpandState(spanId: string): [boolean, () => void] {
  const { expandAll, expandedIds, toggleExpand } = useFullscreen();
  const expanded = expandAll || expandedIds.has(spanId);
  return [expanded, () => toggleExpand(spanId)];
}
