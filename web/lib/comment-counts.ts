"use client";

import { useEffect, useState } from "react";
import type { TrajectoryDetail } from "./api";
import { listComments } from "./collab";

/**
 * Fetches comment counts per span for the given trajectory. One request per
 * span, parallelized — simple v1 at dogfood scale. A single aggregated
 * endpoint is a v-next optimization (see spec follow-ups).
 */
export function useCommentCounts(
  trajectory: TrajectoryDetail | undefined,
): Map<string, number> {
  const [counts, setCounts] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    if (!trajectory) return;
    let cancelled = false;
    const ids = trajectory.spans.map((s) => s.span_id);
    Promise.all(
      ids.map(async (spanId) => {
        try {
          const rows = await listComments(trajectory.id, spanId);
          return [spanId, rows.length] as const;
        } catch {
          return [spanId, 0] as const;
        }
      }),
    ).then((pairs) => {
      if (cancelled) return;
      const next = new Map<string, number>();
      for (const [id, n] of pairs) if (n > 0) next.set(id, n);
      setCounts(next);
    });
    return () => {
      cancelled = true;
    };
  }, [trajectory]);

  return counts;
}
