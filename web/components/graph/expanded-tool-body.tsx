"use client";

import type { Span } from "@/lib/api";
import { extractToolFields } from "@/lib/span-fields";

const MAX = 200;

export function ExpandedToolBody({ span }: { span: Span }) {
  const f = extractToolFields(span.attributes);
  const input = f.input ?? f.parameters;
  const output = f.output;

  // Neither OpenInference (`input.value`/`output.value`) nor the SDK's
  // own `langperf.tool.args`/`langperf.tool.result` were stamped —
  // user is wrapping with `langperf.node(kind="tool_call")` as a bare
  // context manager, which only emits the tool name. Show a gentle
  // hint rather than dumping the raw attrs bag.
  if (input == null && output == null) {
    return (
      <div
        data-expanded-body
        className="text-[11px] text-warm-fog/60 italic leading-relaxed"
      >
        No args or result captured on this span. Tool name:{" "}
        <span className="font-mono text-warm-fog">
          {f.tool_name ?? span.name ?? "(unknown)"}
        </span>
        .
        <div className="mt-1 text-[10px] text-patina not-italic">
          Use <code className="text-aether-teal">@langperf.tool</code> to
          auto-capture args + result, or set{" "}
          <code className="text-aether-teal">langperf.tool.args</code> /{" "}
          <code className="text-aether-teal">langperf.tool.result</code> on the
          span.
        </div>
      </div>
    );
  }

  return (
    <div data-expanded-body className="text-[11px]">
      {input != null ? <Block label="ARGS IN" value={input} /> : null}
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
