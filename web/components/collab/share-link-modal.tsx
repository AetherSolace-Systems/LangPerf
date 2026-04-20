"use client";

import { useEffect, useRef, useState } from "react";

import { createShareLink } from "@/lib/collab";

const FOCUSABLE_SELECTOR =
  '[tabindex]:not([tabindex="-1"]), input:not([disabled]), button:not([disabled]), [href], select:not([disabled]), textarea:not([disabled])';

export function ShareLinkModal({ trajectoryId }: { trajectoryId: string }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const modalRef = useRef<HTMLDivElement | null>(null);

  async function generate() {
    const { token } = await createShareLink(trajectoryId);
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    setUrl(`${origin}/shared/${token}`);
  }

  useEffect(() => {
    if (!open) return;
    const root = modalRef.current;
    if (!root) return;
    const focusables = root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    if (focusables.length > 0) focusables[0].focus();
  }, [open, url]);

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.stopPropagation();
      setOpen(false);
      return;
    }
    if (e.key !== "Tab") return;
    const root = modalRef.current;
    if (!root) return;
    const focusables = Array.from(
      root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((el) => !el.hasAttribute("disabled"));
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement as HTMLElement | null;
    if (e.shiftKey && active === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && active === last) {
      e.preventDefault();
      first.focus();
    }
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
          <div
            ref={modalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="share-link-modal-title"
            onKeyDown={onKeyDown}
            className="w-96 rounded-lg bg-warm-fog/10 p-4 ring-1 ring-warm-fog/20"
            onClick={(e) => e.stopPropagation()}
          >
            <h3
              id="share-link-modal-title"
              className="mb-2 text-sm font-semibold text-aether-teal"
            >
              Share this trajectory
            </h3>
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
