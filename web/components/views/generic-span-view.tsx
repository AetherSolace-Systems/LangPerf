"use client";

import type { Span } from "@/lib/api";
import { fmtDuration } from "@/lib/format";

export function GenericSpanView({ span }: { span: Span }) {
  return (
    <div className="space-y-5">
      <section>
        <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
          Span
        </h3>
        <div className="font-mono text-sm">{span.name}</div>
      </section>

      <section className="grid grid-cols-3 gap-3 text-sm">
        <Stat label="Kind" value={span.kind ?? "—"} />
        <Stat label="Duration" value={fmtDuration(span.duration_ms)} />
        <Stat label="Status" value={span.status_code ?? "—"} />
      </section>

      <section>
        <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
          Attributes
        </h3>
        <pre className="text-xs font-mono whitespace-pre-wrap break-words bg-black/30 border border-[var(--border)] rounded p-3">
          {JSON.stringify(span.attributes, null, 2)}
        </pre>
      </section>

      {span.events && span.events.length > 0 ? (
        <section>
          <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
            Events ({span.events.length})
          </h3>
          <pre className="text-xs font-mono whitespace-pre-wrap break-words bg-black/30 border border-[var(--border)] rounded p-3">
            {JSON.stringify(span.events, null, 2)}
          </pre>
        </section>
      ) : null}
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
