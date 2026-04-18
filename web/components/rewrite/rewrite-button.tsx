"use client";

import { useState } from "react";

import type { Rewrite } from "@/lib/rewrites";
import { RewriteComposer } from "./rewrite-composer";

export function RewriteButton({
  trajectoryId,
  spanId,
  onCreated,
}: {
  trajectoryId: string;
  spanId: string;
  onCreated: (r: Rewrite) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-aether-teal/10 px-2 py-1 text-xs text-aether-teal"
      >
        Propose rewrite
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60" onClick={() => setOpen(false)}>
          <div
            onClick={(e) => e.stopPropagation()}
            className="h-full w-[28rem] overflow-y-auto bg-carbon p-4"
          >
            <RewriteComposer
              trajectoryId={trajectoryId}
              branchSpanId={spanId}
              onCreated={(r) => {
                onCreated(r);
                setOpen(false);
              }}
              onCancel={() => setOpen(false)}
            />
          </div>
        </div>
      )}
    </>
  );
}
