"use client";

import type { Span } from "@/lib/api";
import { fmtDuration } from "@/lib/format";
import { extractLlmFields, type LlmMessage } from "@/lib/span-fields";

const roleStyles: Record<string, string> = {
  system: "bg-amber-500/10 border-amber-500/30 text-amber-200",
  user: "bg-sky-500/10 border-sky-500/30 text-sky-200",
  assistant: "bg-emerald-500/10 border-emerald-500/30 text-emerald-200",
  tool: "bg-violet-500/10 border-violet-500/30 text-violet-200",
  developer: "bg-orange-500/10 border-orange-500/30 text-orange-200",
};

function MessageCard({ message }: { message: LlmMessage }) {
  const cls =
    roleStyles[message.role] ??
    "bg-[var(--border)]/30 border-[var(--border)] text-[var(--foreground)]";
  return (
    <div className={`border rounded-md ${cls}`}>
      <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider border-b border-current/20">
        {message.role}
      </div>
      <div className="p-3 text-sm whitespace-pre-wrap break-words text-[var(--foreground)]/90">
        {message.content ??
          (message.tool_calls?.length ? (
            <span className="text-[var(--muted)] italic">
              (tool calls only)
            </span>
          ) : (
            <span className="text-[var(--muted)] italic">(no content)</span>
          ))}
      </div>
      {message.tool_calls?.length ? (
        <div className="px-3 pb-3 space-y-2">
          {message.tool_calls.map((tc, idx) => (
            <div
              key={idx}
              className="text-xs font-mono bg-black/40 rounded border border-current/20 p-2"
            >
              <div>
                <span className="text-[var(--muted)]">→</span> {tc.name}
                {tc.id ? (
                  <span className="text-[var(--muted)] ml-2">({tc.id})</span>
                ) : null}
              </div>
              <pre className="mt-1 text-[var(--muted)] overflow-x-auto">
                {typeof tc.arguments === "string"
                  ? tc.arguments
                  : JSON.stringify(tc.arguments, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function LlmSpanView({ span }: { span: Span }) {
  const f = extractLlmFields(span.attributes);

  return (
    <div className="space-y-5">
      <section>
        <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
          Model
        </h3>
        <div className="font-mono text-sm">
          {f.system ? (
            <span className="text-[var(--muted)]">{f.system} · </span>
          ) : null}
          {f.model ?? <span className="text-[var(--muted)]">unknown</span>}
        </div>
      </section>

      <section className="grid grid-cols-3 gap-3 text-sm">
        <Stat label="Prompt" value={f.tokens.prompt} suffix="t" />
        <Stat label="Completion" value={f.tokens.completion} suffix="t" />
        <Stat label="Total" value={f.tokens.total} suffix="t" />
        <Stat label="Duration" value={fmtDuration(span.duration_ms)} />
        <Stat label="Status" value={span.status_code ?? "—"} />
        <Stat label="Span kind" value={span.kind ?? "—"} />
      </section>

      {f.input_messages.length > 0 ? (
        <section>
          <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
            Input messages
          </h3>
          <div className="space-y-2">
            {f.input_messages.map((m, i) => (
              <MessageCard key={i} message={m} />
            ))}
          </div>
        </section>
      ) : null}

      {f.output_messages.length > 0 ? (
        <section>
          <h3 className="text-[10px] uppercase tracking-wider text-[var(--muted)] mb-2">
            Output
          </h3>
          <div className="space-y-2">
            {f.output_messages.map((m, i) => (
              <MessageCard key={i} message={m} />
            ))}
          </div>
        </section>
      ) : null}

      {f.invocation_parameters ? (
        <Collapsible title="Invocation parameters">
          <pre className="text-xs font-mono whitespace-pre-wrap break-words">
            {JSON.stringify(f.invocation_parameters, null, 2)}
          </pre>
        </Collapsible>
      ) : null}

      {f.output_raw ? (
        <Collapsible title="Raw response">
          <pre className="text-xs font-mono whitespace-pre-wrap break-words">
            {JSON.stringify(f.output_raw, null, 2)}
          </pre>
        </Collapsible>
      ) : null}

      <Collapsible title="All attributes">
        <pre className="text-xs font-mono whitespace-pre-wrap break-words">
          {JSON.stringify(span.attributes, null, 2)}
        </pre>
      </Collapsible>
    </div>
  );
}

function Stat({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string | number | null;
  suffix?: string;
}) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[var(--muted)]">
        {label}
      </div>
      <div className="font-mono text-sm tabular-nums mt-0.5">
        {value == null ? "—" : value}
        {value != null && suffix ? suffix : ""}
      </div>
    </div>
  );
}

function Collapsible({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <details className="border border-[var(--border)] rounded-md">
      <summary className="cursor-pointer px-3 py-2 text-xs uppercase tracking-wider text-[var(--muted)] select-none">
        {title}
      </summary>
      <div className="px-3 pb-3 bg-black/20">{children}</div>
    </details>
  );
}
