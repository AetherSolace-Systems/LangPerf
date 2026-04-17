/**
 * Pull well-known fields out of the heterogeneous attribute bag.
 *
 * Spans come from at least three overlapping conventions:
 *   - OTel GenAI semconv   (gen_ai.*)
 *   - OpenInference         (llm.*, input.*, output.*, openinference.*)
 *   - LangPerf SDK          (langperf.*)
 *
 * This module centralizes attribute access so components don't each know all
 * three namespaces.
 */

import type { Span } from "@/lib/api";
import { safeJsonParse } from "@/lib/format";

type Attrs = Span["attributes"];

export type Role = "system" | "user" | "assistant" | "tool" | "developer" | string;

export type LlmMessage = {
  role: Role;
  content: string | null;
  tool_calls?: Array<{
    name: string;
    arguments: string | Record<string, unknown>;
    id?: string;
  }>;
};

export type LlmSpanFields = {
  system: string | null; // "openai" / "anthropic" / etc.
  model: string | null;
  invocation_parameters: Record<string, unknown> | null;
  input_messages: LlmMessage[];
  output_messages: LlmMessage[];
  tokens: {
    prompt: number | null;
    completion: number | null;
    total: number | null;
  };
  input_raw: unknown;
  output_raw: unknown;
};

export type ToolSpanFields = {
  tool_name: string | null;
  tool_description: string | null;
  parameters: unknown;
  input: unknown;
  output: unknown;
};

export function kindOf(span: Span): string {
  const attrs = span.attributes;
  const explicit = (attrs["langperf.node.kind"] as string | undefined) ?? null;
  if (explicit) return explicit.toLowerCase();
  const oi = (attrs["openinference.span.kind"] as string | undefined) ?? null;
  if (oi) return oi.toLowerCase();
  if (span.kind) return span.kind.toLowerCase();
  if ("gen_ai.operation.name" in attrs || "llm.system" in attrs) return "llm";
  if ("tool.name" in attrs) return "tool";
  return "generic";
}

/**
 * Total tokens for a span, checking both OpenInference (`llm.token_count.total`)
 * and OTel GenAI (`gen_ai.usage.total_tokens`) conventions. Returns null when
 * neither is present (e.g. non-LLM span, or local model that didn't report
 * usage). Prefer this over re-implementing the fallback chain per caller.
 */
export function extractTotalTokens(span: Span | null | undefined): number | null {
  if (!span) return null;
  const attrs = span.attributes;
  const t =
    (attrs["llm.token_count.total"] as number | undefined) ??
    (attrs["gen_ai.usage.total_tokens"] as number | undefined);
  return typeof t === "number" ? t : null;
}

export function extractLlmFields(attrs: Attrs): LlmSpanFields {
  const system =
    (attrs["llm.system"] as string) ??
    (attrs["gen_ai.system"] as string) ??
    null;
  const model =
    (attrs["llm.model_name"] as string) ??
    (attrs["gen_ai.request.model"] as string) ??
    (attrs["gen_ai.response.model"] as string) ??
    null;

  const invocation_parameters = (() => {
    const raw = attrs["llm.invocation_parameters"];
    const parsed = safeJsonParse(raw);
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : null;
  })();

  const input_messages = readIndexedMessages(attrs, "llm.input_messages");
  const output_messages = readIndexedMessages(attrs, "llm.output_messages");

  const tokens = {
    prompt: numOrNull(attrs["llm.token_count.prompt"] ?? attrs["gen_ai.usage.input_tokens"]),
    completion: numOrNull(attrs["llm.token_count.completion"] ?? attrs["gen_ai.usage.output_tokens"]),
    total: numOrNull(attrs["llm.token_count.total"] ?? attrs["gen_ai.usage.total_tokens"]),
  };

  return {
    system,
    model,
    invocation_parameters,
    input_messages,
    output_messages,
    tokens,
    input_raw: safeJsonParse(attrs["input.value"]),
    output_raw: safeJsonParse(attrs["output.value"]),
  };
}

export function extractToolFields(attrs: Attrs): ToolSpanFields {
  return {
    tool_name: (attrs["tool.name"] as string) ?? null,
    tool_description: (attrs["tool.description"] as string) ?? null,
    parameters: safeJsonParse(attrs["tool.parameters"]),
    input: safeJsonParse(attrs["input.value"]),
    output: safeJsonParse(attrs["output.value"]),
  };
}

function numOrNull(v: unknown): number | null {
  if (typeof v === "number") return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function readIndexedMessages(attrs: Attrs, prefix: string): LlmMessage[] {
  // OpenInference flattens messages into:
  //   <prefix>.<i>.message.role
  //   <prefix>.<i>.message.content
  //   <prefix>.<i>.message.tool_calls.<j>.tool_call.function.name
  //   <prefix>.<i>.message.tool_calls.<j>.tool_call.function.arguments
  const messages: LlmMessage[] = [];
  const indexes = new Set<number>();
  for (const key of Object.keys(attrs)) {
    if (!key.startsWith(`${prefix}.`)) continue;
    const tail = key.slice(prefix.length + 1);
    const idx = parseInt(tail.split(".")[0], 10);
    if (Number.isFinite(idx)) indexes.add(idx);
  }

  const sorted = [...indexes].sort((a, b) => a - b);
  for (const i of sorted) {
    const base = `${prefix}.${i}.message`;
    const role = (attrs[`${base}.role`] as string) ?? "unknown";
    const content = (attrs[`${base}.content`] as string | null) ?? null;

    const tool_calls: NonNullable<LlmMessage["tool_calls"]> = [];
    const tcIndexes = new Set<number>();
    for (const key of Object.keys(attrs)) {
      const tcPrefix = `${base}.tool_calls.`;
      if (!key.startsWith(tcPrefix)) continue;
      const tcIdx = parseInt(key.slice(tcPrefix.length).split(".")[0], 10);
      if (Number.isFinite(tcIdx)) tcIndexes.add(tcIdx);
    }
    for (const j of [...tcIndexes].sort((a, b) => a - b)) {
      const tb = `${base}.tool_calls.${j}.tool_call`;
      tool_calls.push({
        name: (attrs[`${tb}.function.name`] as string) ?? "unknown",
        arguments: safeJsonParse(attrs[`${tb}.function.arguments`]) as
          | string
          | Record<string, unknown>,
        id: (attrs[`${tb}.id`] as string | undefined) ?? undefined,
      });
    }

    messages.push({
      role,
      content,
      tool_calls: tool_calls.length ? tool_calls : undefined,
    });
  }
  return messages;
}
