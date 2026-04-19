"use client";

import { useSelection } from "@/components/selection-context";
import { kindOf, extractToolFields, extractLlmFields } from "@/lib/span-fields";
import { fmtDuration } from "@/lib/format";
import type { Span } from "@/lib/api";

export function FloatingInspector({ onOpenFull }: { onOpenFull: () => void }) {
  const { selectedSpan: span } = useSelection();
  if (!span) return null;

  const kind = kindOf(span);

  return (
    <div
      data-floating-inspector=""
      className="absolute bottom-3 right-3 w-[260px] rounded-md border shadow-xl p-3 z-20 pointer-events-auto"
      style={{
        background: "var(--surface)",
        borderColor: "var(--border)",
        borderLeftWidth: 3,
        borderLeftColor: kind === "tool" ? "#E8A87C" : "#6BBAB1",
      }}
    >
      <div className="flex items-center gap-2 text-[9px] uppercase tracking-wider text-warm-fog/60">
        <span>{kind}</span>
        <span className="text-warm-fog/90 font-medium normal-case text-[11px] tracking-normal truncate">
          {span.name}
        </span>
        <span className="ml-auto font-mono">{fmtDuration(span.duration_ms)}</span>
      </div>
      <div className="mt-2 space-y-1 font-mono text-[10px] text-warm-fog/90 break-words">
        {kind === "tool" ? <ToolPreview span={span} /> : null}
        {kind === "llm" ? <LlmPreview span={span} /> : null}
      </div>
      <button
        type="button"
        onClick={onOpenFull}
        className="mt-2 text-[10px] text-aether-teal hover:underline"
      >
        open full detail →
      </button>
    </div>
  );
}

function ToolPreview({ span }: { span: Span }) {
  const f = extractToolFields(span.attributes);
  const input = f.input ?? f.parameters ?? null;
  const output = f.output ?? null;
  return (
    <>
      {input != null ? (
        <div>
          <span className="text-warm-fog/50">args</span>{" "}
          {truncate(JSON.stringify(input), 80)}
        </div>
      ) : null}
      {output != null ? (
        <div>
          <span className="text-warm-fog/50">out</span>{" "}
          {truncate(JSON.stringify(output), 80)}
        </div>
      ) : null}
    </>
  );
}

function LlmPreview({ span }: { span: Span }) {
  const f = extractLlmFields(span.attributes);
  const last = f.output_messages[f.output_messages.length - 1];
  const preview = last?.content ?? "(no output)";
  return (
    <div>
      <span className="text-warm-fog/50">out</span> {truncate(preview, 120)}
    </div>
  );
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
