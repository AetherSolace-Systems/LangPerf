"use client";

import type { Span } from "@/lib/api";
import { extractToolFields } from "@/lib/span-fields";

const MAX = 200;

export function ExpandedToolBody({ span }: { span: Span }) {
  const f = extractToolFields(span.attributes);
  const input = f.input ?? f.parameters ?? span.attributes;
  const output = f.output;

  return (
    <div data-expanded-body className="text-[11px]">
      <Block label="ARGS IN" value={input} />
      {output != null ? <Block label="RESULT OUT" value={output} /> : null}
    </div>
  );
}

function Block({ label, value }: { label: string; value: unknown }) {
  const pretty =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const truncated = pretty.length > MAX ? pretty.slice(0, MAX) + "…" : pretty;
  return (
    <div className="mb-2 last:mb-0">
      <div className="text-[9px] uppercase tracking-wider text-warm-fog/60 mb-1">
        {label}
      </div>
      <pre
        className="font-mono text-[10px] whitespace-pre-wrap break-words p-2 rounded"
        style={{
          background: "var(--background)",
          border: "1px solid var(--border)",
          color: "var(--foreground)",
          lineHeight: 1.5,
        }}
      >
        {truncated}
      </pre>
    </div>
  );
}
