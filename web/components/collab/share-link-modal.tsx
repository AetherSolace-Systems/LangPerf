"use client";

import { useState } from "react";

import { createShareLink } from "@/lib/collab";

export function ShareLinkModal({ trajectoryId }: { trajectoryId: string }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState<string | null>(null);

  async function generate() {
    const { token } = await createShareLink(trajectoryId);
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    setUrl(`${origin}/shared/${token}`);
  }

  return (
    <>
      <button
        onClick={() => { setOpen(true); if (!url) generate(); }}
        className="rounded bg-warm-fog/10 px-2 py-1 text-xs text-warm-fog hover:bg-warm-fog/20"
      >
        Share
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setOpen(false)}>
          <div className="w-96 rounded-lg bg-warm-fog/10 p-4 ring-1 ring-warm-fog/20" onClick={(e) => e.stopPropagation()}>
            <h3 className="mb-2 text-sm font-semibold text-aether-teal">Share this trajectory</h3>
            {url ? (
              <div className="space-y-2">
                <input readOnly value={url} className="w-full rounded bg-carbon px-3 py-2 text-xs text-warm-fog" />
                <p className="text-[0.65rem] text-warm-fog/50">Anyone signed into your org can open this link.</p>
              </div>
            ) : (
              <p className="text-xs text-warm-fog/60">Generating link\u2026</p>
            )}
          </div>
        </div>
      )}
    </>
  );
}
