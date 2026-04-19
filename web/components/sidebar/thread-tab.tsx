"use client";

import type { Span, TrajectoryDetail } from "@/lib/api";
import { CommentThread } from "@/components/collab/comment-thread";

export function ThreadTab({
  span,
  trajectory,
}: {
  span: Span | null;
  trajectory?: TrajectoryDetail;
}) {
  if (!trajectory) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">Loading trajectory…</div>
    );
  }
  if (!span) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Select a node to join the conversation.
      </div>
    );
  }
  return (
    <div className="p-5">
      <CommentThread trajectoryId={trajectory.id} spanId={span.span_id} />
    </div>
  );
}
