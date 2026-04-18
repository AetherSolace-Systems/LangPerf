"use client";

import { useState } from "react";

export function CommentComposer({ onSubmit }: { onSubmit: (body: string) => Promise<void> }) {
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);

  async function submit() {
    if (!body.trim()) return;
    setPending(true);
    try {
      await onSubmit(body);
      setBody("");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Leave a comment. @mention to notify a teammate."
        rows={3}
        className="w-full resize-none rounded-lg bg-carbon p-3 text-sm text-warm-fog ring-1 ring-warm-fog/10 focus:outline-none focus:ring-aether-teal"
      />
      <button
        onClick={submit}
        disabled={pending || !body.trim()}
        className="self-end rounded bg-aether-teal px-3 py-1 text-xs font-semibold text-carbon disabled:opacity-50"
      >
        {pending ? "Posting\u2026" : "Post"}
      </button>
    </div>
  );
}
