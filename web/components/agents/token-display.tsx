"use client";

import { useState } from "react";

export function TokenDisplay({ token }: { token: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <div className="rounded-md border border-peach-neon/40 bg-peach-neon/5 p-3">
      <div className="mb-2 text-xs font-semibold text-peach-neon">
        Save this token — you won&apos;t see it again
      </div>
      <div className="flex items-center gap-2">
        <code className="flex-1 break-all rounded bg-carbon px-2 py-1 font-mono text-xs text-warm-fog">
          {token}
        </code>
        <button
          type="button"
          onClick={copy}
          className="rounded bg-aether-teal px-2 py-1 text-xs font-semibold text-carbon"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
