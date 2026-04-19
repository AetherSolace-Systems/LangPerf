"use client";

import type { Span } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { GenericSpanView } from "@/components/views/generic-span-view";
import { LlmSpanView } from "@/components/views/llm-span-view";
import { ToolSpanView } from "@/components/views/tool-span-view";

export function DetailTab({ span }: { span: Span | null }) {
  if (!span) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Select a node in the graph or tree to see its detail.
      </div>
    );
  }
  const kind = kindOf(span);
  return (
    <div className="p-5">
      {kind === "llm" ? <LlmSpanView span={span} /> : null}
      {kind === "tool" ? <ToolSpanView span={span} /> : null}
      {kind !== "llm" && kind !== "tool" ? <GenericSpanView span={span} /> : null}
    </div>
  );
}
