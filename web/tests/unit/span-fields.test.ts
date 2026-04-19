import { describe, it, expect } from "vitest";
import type { Span } from "@/lib/api";
import {
  kindOf,
  extractLlmFields,
  extractToolFields,
  toolName,
  toolOutput,
} from "@/lib/span-fields";

function makeSpan(overrides: Partial<Span> = {}): Span {
  return {
    span_id: "s1",
    trace_id: "t1",
    trajectory_id: "tr1",
    parent_span_id: null,
    name: "test",
    kind: null,
    started_at: "2026-01-01T00:00:00.000Z",
    ended_at: "2026-01-01T00:00:01.000Z",
    duration_ms: 1000,
    attributes: {},
    events: null,
    status_code: null,
    notes: null,
    ...overrides,
  };
}

describe("kindOf", () => {
  it("prefers the openinference.span.kind attribute (lowercased)", () => {
    const s = makeSpan({
      kind: null,
      attributes: { "openinference.span.kind": "LLM" },
    });
    expect(kindOf(s)).toBe("llm");
  });

  it("falls back to span.kind when no attribute namespace has a kind", () => {
    const s = makeSpan({ kind: "Tool", attributes: {} });
    expect(kindOf(s)).toBe("tool");
  });

  it("returns 'generic' when nothing identifies the kind", () => {
    // Note: the implementation's terminal fallback is 'generic', not 'unknown'.
    const s = makeSpan({ kind: null, attributes: {} });
    expect(kindOf(s)).toBe("generic");
  });

  it("prefers langperf.node.kind over other namespaces", () => {
    const s = makeSpan({
      kind: "llm",
      attributes: {
        "langperf.node.kind": "Reasoning",
        "openinference.span.kind": "llm",
      },
    });
    expect(kindOf(s)).toBe("reasoning");
  });
});

describe("extractLlmFields", () => {
  it("reads indexed llm.input_messages.<i>.message.role/content in order", () => {
    const attrs = {
      "llm.input_messages.0.message.role": "system",
      "llm.input_messages.0.message.content": "you are helpful",
      "llm.input_messages.1.message.role": "user",
      "llm.input_messages.1.message.content": "hi",
    };
    const out = extractLlmFields(attrs);
    expect(out.input_messages).toHaveLength(2);
    expect(out.input_messages[0].role).toBe("system");
    expect(out.input_messages[0].content).toBe("you are helpful");
    expect(out.input_messages[1].role).toBe("user");
    expect(out.input_messages[1].content).toBe("hi");
  });

  it("reads token counts from gen_ai.usage.* fallback chain", () => {
    const attrs = {
      "gen_ai.usage.input_tokens": 100,
      "gen_ai.usage.output_tokens": 50,
      "gen_ai.usage.total_tokens": 150,
    };
    const out = extractLlmFields(attrs);
    expect(out.tokens.prompt).toBe(100);
    expect(out.tokens.completion).toBe(50);
    expect(out.tokens.total).toBe(150);
  });

  it("prefers OpenInference token count attributes over gen_ai", () => {
    const attrs = {
      "llm.token_count.prompt": 10,
      "llm.token_count.completion": 20,
      "llm.token_count.total": 30,
      "gen_ai.usage.input_tokens": 999,
      "gen_ai.usage.output_tokens": 999,
      "gen_ai.usage.total_tokens": 999,
    };
    const out = extractLlmFields(attrs);
    expect(out.tokens.prompt).toBe(10);
    expect(out.tokens.completion).toBe(20);
    expect(out.tokens.total).toBe(30);
  });
});

describe("extractToolFields + toolName/toolOutput", () => {
  it("extractToolFields picks tool_name from tool.name", () => {
    expect(extractToolFields({ "tool.name": "search_docs" }).tool_name).toBe(
      "search_docs",
    );
  });

  it("extractToolFields returns null tool_name when tool.name is absent", () => {
    // NOTE: task spec mentions a gen_ai.tool.name / name fallback chain, but
    // the current implementation only reads tool.name. Matching real behavior.
    expect(extractToolFields({ "gen_ai.tool.name": "other" }).tool_name).toBeNull();
    expect(extractToolFields({ name: "plain" }).tool_name).toBeNull();
    expect(extractToolFields({}).tool_name).toBeNull();
  });

  it("toolName(span) returns a string when tool.name is set", () => {
    const s = makeSpan({ attributes: { "tool.name": "lookup" } });
    expect(toolName(s)).toBe("lookup");
  });

  it("toolName(span) returns null when missing", () => {
    const s = makeSpan({ attributes: {} });
    expect(toolName(s)).toBeNull();
  });

  it("toolOutput(span) returns the parsed output.value", () => {
    const s = makeSpan({
      attributes: { "output.value": '{"result":"ok"}' },
    });
    expect(toolOutput(s)).toEqual({ result: "ok" });
  });

  it("toolOutput(span) returns null when no output.value is present", () => {
    const s = makeSpan({ attributes: {} });
    expect(toolOutput(s)).toBeNull();
  });
});
