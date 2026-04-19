"use client";

import type { LayoutNode } from "@/lib/sequence-layout";
import { fmtDuration } from "@/lib/format";

export function ExpandedFrameBody({ layout }: { layout: LayoutNode }) {
  const { label, span } = layout;
  return (
    <div data-expanded-body className="text-[11px] text-warm-fog/70">
      <span className="font-mono">{label}</span>
      {span?.duration_ms != null ? (
        <span className="ml-2 font-mono text-warm-fog/50">
          · {fmtDuration(span.duration_ms)}
        </span>
      ) : null}
    </div>
  );
}
