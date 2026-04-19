"use client";

import type { Span } from "@/lib/api";
import { fmtDuration } from "@/lib/format";
import { extractToolFields } from "@/lib/span-fields";

export function ToolSpanView({ span }: { span: Span }) {
  const f = extractToolFields(span.attributes);

  return (
    <div className="space-y-5">
      <section>
        <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
          Tool
        </h3>
        <div className="font-mono text-sm">
          {f.tool_name ?? span.name}
        </div>
        {f.tool_description ? (
          <div className="text-xs text-[var(--muted)] mt-1">
            {f.tool_description}
          </div>
        ) : null}
      </section>

      <section className="grid grid-cols-3 gap-3 text-sm">
        <Stat label="Duration" value={fmtDuration(span.duration_ms)} />
        <Stat label="Status" value={span.status_code ?? "—"} />
        <Stat label="Span kind" value={span.kind ?? "tool"} />
      </section>

      <section>
        <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
          Input
        </h3>
        <CodeBlock value={f.input ?? f.parameters ?? span.attributes} />
      </section>

      {f.output !== undefined && f.output !== null ? (
        <section>
          <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
            Output
          </h3>
          <CodeBlock value={f.output} />
        </section>
      ) : null}

      <details className="border border-[var(--border)] rounded-md">
        <summary className="cursor-pointer px-3 py-2 text-xs uppercase tracking-wider text-[var(--muted)] select-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-aether-teal focus-visible:outline-offset-2 rounded-sm">
          All attributes
        </summary>
        <div className="px-3 pb-3 bg-black/20">
          <pre className="text-xs font-mono whitespace-pre-wrap break-words">
            {JSON.stringify(span.attributes, null, 2)}
          </pre>
        </div>
      </details>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">
        {label}
      </div>
      <div className="font-mono text-sm tabular-nums mt-0.5">{value ?? "—"}</div>
    </div>
  );
}

function CodeBlock({ value }: { value: unknown }) {
  const str =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <pre className="text-xs font-mono whitespace-pre-wrap break-words bg-black/30 border border-[var(--border)] rounded p-3">
      {str}
    </pre>
  );
}
