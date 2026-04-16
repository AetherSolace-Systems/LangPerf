"use client";

import type { Span } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { GenericSpanView } from "@/components/views/generic-span-view";
import { LlmSpanView } from "@/components/views/llm-span-view";
import { ToolSpanView } from "@/components/views/tool-span-view";

export function NodeDetailPanel({ span }: { span: Span | null }) {
  if (!span) {
    return (
      <div className="p-6 text-sm text-[var(--muted)]">
        Select a node in the tree to see details.
      </div>
    );
  }

  const kind = kindOf(span);

  return (
    <div className="h-full overflow-y-auto">
      <header className="border-b border-[var(--border)] px-5 py-3">
        <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">
          {kind}
        </div>
        <div className="text-sm font-medium mt-0.5 truncate">{span.name}</div>
        <div className="text-[10px] font-mono text-[var(--muted)] mt-1">
          {span.span_id}
        </div>
      </header>
      <div className="p-5">
        {kind === "llm" ? (
          <LlmSpanView span={span} />
        ) : kind === "tool" ? (
          <ToolSpanView span={span} />
        ) : (
          <GenericSpanView span={span} />
        )}
      </div>
    </div>
  );
}
