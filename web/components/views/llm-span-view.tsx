"use client";

import type { Span } from "@/lib/api";
import { roleSwatch } from "@/lib/colors";
import { fmtDuration } from "@/lib/format";
import { extractLlmFields, type LlmMessage } from "@/lib/span-fields";

function MessageCard({ message }: { message: LlmMessage }) {
  const swatch = roleSwatch(message.role);
  const reasoning = message.reasoning?.trim();
  return (
    <div
      className="border rounded-md"
      style={{ borderColor: swatch.border, background: swatch.bg }}
    >
      <div
        className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider border-b"
        style={{ color: swatch.fg, borderColor: swatch.border }}
      >
        {message.role}
      </div>
      {reasoning ? (
        // Thinking / reasoning surfaces for OpenAI o-series, Anthropic
        // extended thinking, and Gemini. The flat
        // `llm.input_messages.<i>.message.content` attr is empty when
        // the model reasons then emits only tool_calls; this block is
        // often the only place the thinking shows up. Violet signals
        // "reasoning channel" distinct from the role-colored body.
        <div
          className="px-3 py-2 border-b text-sm italic whitespace-pre-wrap break-words text-aether-violet/85"
          style={{
            borderColor: swatch.border,
            background: "rgba(167,139,250,0.06)",
          }}
        >
          <span
            className="text-[9px] uppercase tracking-wider not-italic font-mono mr-2 px-1 rounded text-aether-violet"
            style={{
              letterSpacing: "0.08em",
              border: "1px solid rgba(167,139,250,0.55)",
            }}
          >
            tnk
          </span>
          {reasoning}
        </div>
      ) : null}
      <div className="p-3 text-sm whitespace-pre-wrap break-words text-warm-fog/90">
        {message.content ??
          (message.tool_calls?.length ? (
            <span className="text-patina italic">(tool calls only)</span>
          ) : (
            <span className="text-patina italic">(no content)</span>
          ))}
      </div>
      {message.tool_calls?.length ? (
        <div className="px-3 pb-3 space-y-2">
          {message.tool_calls.map((tc, idx) => (
            <div
              key={idx}
              className="text-xs font-mono bg-carbon/60 rounded border p-2"
              style={{ borderColor: swatch.border }}
            >
              <div style={{ color: swatch.fg }}>
                <span className="text-patina">→</span> {tc.name}
                {tc.id ? (
                  <span className="text-patina ml-2">({tc.id})</span>
                ) : null}
              </div>
              <pre className="mt-1 text-patina overflow-x-auto">
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
        <h3 className="text-[10px] uppercase tracking-wider text-patina mb-2">
          Model
        </h3>
        <div className="font-mono text-sm">
          {f.system ? (
            <span className="text-patina">{f.system} · </span>
          ) : null}
          {f.model ?? <span className="text-patina">unknown</span>}
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
          <h3 className="text-[10px] uppercase tracking-wider text-patina mb-2">
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
          <h3 className="text-[10px] uppercase tracking-wider text-patina mb-2">
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
      <div className="text-[10px] uppercase tracking-wider text-patina">
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
    <details className="border border-[color:var(--border)] rounded-md">
      <summary className="cursor-pointer px-3 py-2 text-xs uppercase tracking-wider text-patina select-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-aether-teal focus-visible:outline-offset-2 rounded-sm">
        {title}
      </summary>
      <div className="px-3 pb-3 bg-carbon/50">{children}</div>
    </details>
  );
}
