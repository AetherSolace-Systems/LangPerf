"use client";

import type { Span } from "@/lib/api";
import { extractLlmFields, type LlmMessage } from "@/lib/span-fields";
import { roleSwatch } from "@/lib/colors";

const MSG_MAX = 120;

export function ExpandedLlmBody({ span }: { span: Span }) {
  const f = extractLlmFields(span.attributes);

  return (
    <div data-expanded-body className="text-[11px]">
      {f.input_messages.length > 0 ? (
        <div className="mb-2">
          <div className="text-[9px] uppercase tracking-wider text-warm-fog/60 mb-1">
            INPUT
          </div>
          <div className="space-y-1">
            {f.input_messages.map((m, i) => (
              <MsgLine key={i} message={m} />
            ))}
          </div>
        </div>
      ) : null}

      {f.output_messages.length > 0 ? (
        <div className="mb-2">
          <div className="text-[9px] uppercase tracking-wider text-warm-fog/60 mb-1">
            OUTPUT
          </div>
          <div className="space-y-1">
            {f.output_messages.map((m, i) => (
              <MsgLine key={i} message={m} />
            ))}
          </div>
        </div>
      ) : null}

      <div
        className="flex gap-3 pt-2 mt-2 font-mono text-[10px] text-warm-fog/60"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        {f.tokens.prompt != null ? (
          <span>
            prompt <span className="text-warm-fog">{f.tokens.prompt}t</span>
          </span>
        ) : null}
        {f.tokens.completion != null ? (
          <span>
            compl <span className="text-warm-fog">{f.tokens.completion}t</span>
          </span>
        ) : null}
        {f.model ? (
          <span className="truncate">
            model <span className="text-warm-fog">{f.model}</span>
          </span>
        ) : null}
      </div>
    </div>
  );
}

function MsgLine({ message }: { message: LlmMessage }) {
  const sw = roleSwatch(message.role);
  const content = message.content ?? "";
  const truncated =
    content.length > MSG_MAX ? content.slice(0, MSG_MAX) + "…" : content;
  const reasoning = message.reasoning?.trim();
  const reasoningTrunc =
    reasoning && reasoning.length > MSG_MAX
      ? reasoning.slice(0, MSG_MAX) + "…"
      : reasoning ?? null;

  return (
    <div className="space-y-1">
      {reasoningTrunc ? (
        // TNK row — 3-char label so it column-aligns with SYS/USR/ASST
        // pills on the same card. Solid violet border matches the
        // role-pill styling. Violet ("aether-violet") signals reasoning
        // as a distinct channel from teal assistant / peach tool.
        <div className="flex items-start gap-1.5 leading-relaxed">
          <span
            className="text-[9px] uppercase tracking-wider font-mono flex-shrink-0 px-1 rounded text-aether-violet"
            style={{ border: "1px solid rgba(167,139,250,0.55)" }}
          >
            tnk
          </span>
          <span className="flex-1 text-warm-fog whitespace-pre-wrap">
            {reasoningTrunc}
          </span>
        </div>
      ) : null}
      <div className="flex items-start gap-1.5 leading-relaxed">
        <span
          className="text-[9px] uppercase tracking-wider font-mono flex-shrink-0 px-1 rounded"
          style={{ color: sw.fg, border: `1px solid ${sw.border}` }}
        >
          {roleLabel(message.role)}
        </span>
        <span className="flex-1 text-warm-fog truncate">{truncated}</span>
        {message.tool_calls?.length ? (
          <span className="text-peach-neon flex-shrink-0 font-mono">
            → {message.tool_calls.map((tc) => tc.name).join(", ")}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function roleLabel(role: string): string {
  switch (role.toLowerCase()) {
    case "system": return "sys";
    case "user": return "usr";
    case "assistant": return "asst";
    case "tool": return "tool";
    default: return role.slice(0, 4);
  }
}
