"use client";

import { useEffect, useState } from "react";

import { type Comment, createComment, listComments, resolveComment } from "@/lib/collab";
import { CommentComposer } from "./comment-composer";

export function CommentThread({
  trajectoryId,
  spanId,
}: {
  trajectoryId: string;
  spanId: string;
}) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listComments(trajectoryId, spanId).then((res) => {
      if (!cancelled) { setComments(res); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [trajectoryId, spanId]);

  async function onSubmit(body: string) {
    const created = await createComment(trajectoryId, spanId, body);
    setComments((prev) => [...prev, created]);
  }

  async function onResolve(id: string) {
    const updated = await resolveComment(id);
    setComments((prev) => prev.map((c) => (c.id === id ? updated : c)));
  }

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-warm-fog/70">Comments</h3>
      {loading && <p className="text-xs text-warm-fog/50">Loading\u2026</p>}
      <ul className="flex flex-col gap-2">
        {comments.map((c) => (
          <li
            key={c.id}
            className={`rounded-lg bg-warm-fog/5 p-3 text-sm ring-1 ring-warm-fog/10 ${
              c.resolved ? "opacity-50" : ""
            }`}
          >
            <div className="flex items-center justify-between text-xs text-warm-fog/60">
              <span className="font-medium text-aether-teal">{c.author_display_name}</span>
              <div className="flex items-center gap-2">
                <span>{new Date(c.created_at).toLocaleString()}</span>
                {!c.resolved && (
                  <button className="text-xs text-peach-neon" onClick={() => onResolve(c.id)}>
                    resolve
                  </button>
                )}
              </div>
            </div>
            <p className="mt-1 whitespace-pre-wrap text-warm-fog">{c.body}</p>
          </li>
        ))}
      </ul>
      <CommentComposer onSubmit={onSubmit} />
    </div>
  );
}
