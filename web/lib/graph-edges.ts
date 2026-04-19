import type { Edge } from "@xyflow/react";
import type { Span } from "./api";
import { kindOf } from "./span-fields";

export type LabelledEdgeData = {
  label: string;
  payload?: string;
};

export function buildEdges(spans: Span[]): Edge<LabelledEdgeData>[] {
  const byParent = new Map<string | null, Span[]>();
  for (const s of spans) {
    const key = s.parent_span_id;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key)!.push(s);
  }

  const edges: Edge<LabelledEdgeData>[] = [];
  for (const siblings of byParent.values()) {
    siblings.sort(
      (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
    );
    for (let i = 1; i < siblings.length; i++) {
      const from = siblings[i - 1];
      const to = siblings[i];
      const label = edgeLabel(from, to);
      const payload = edgePayload(from, to);
      edges.push({
        id: `e-${from.span_id}-${to.span_id}`,
        source: from.span_id,
        target: to.span_id,
        sourceHandle: "s-br",
        targetHandle: "t-tl",
        type: "labelled",
        data: { label, payload },
      });
    }
  }
  return edges;
}

function edgeLabel(from: Span, to: Span): string {
  const fromKind = kindOf(from);
  const toKind = kindOf(to);
  if (fromKind === "llm" && toKind === "tool") {
    const name = toolName(to) ?? "tool";
    return `tool:${name}`;
  }
  if (fromKind === "tool" && toKind === "llm") return "return";
  if (fromKind === "llm" && toKind === "llm") return "message";
  if (toKind === "agent") return `delegate:${to.name ?? "agent"}`;
  if (fromKind === "agent") return "resume";
  if (fromKind === "tool" && toKind === "tool") return "next-tool";
  return "next";
}

function toolName(span: Span): string | null {
  const attrs = span.attributes as Record<string, unknown> | null;
  if (!attrs) return null;
  for (const k of ["tool.name", "gen_ai.tool.name", "name"]) {
    const v = attrs[k];
    if (typeof v === "string" && v) return v;
  }
  return null;
}

function edgePayload(from: Span, to: Span): string | undefined {
  const fromKind = kindOf(from);
  const toKind = kindOf(to);
  if (fromKind === "llm" && toKind === "tool") {
    const input = firstToolInput(to);
    return input ? truncate(pretty(input), 50) : undefined;
  }
  if (fromKind === "tool" && toKind === "llm") {
    const out = toolOutput(from);
    return out != null ? truncate(pretty(out), 50) : undefined;
  }
  return undefined;
}

function firstToolInput(span: Span): unknown {
  const a = span.attributes as Record<string, unknown> | null;
  if (!a) return null;
  for (const k of ["tool.arguments", "gen_ai.tool.arguments", "input", "parameters"]) {
    if (a[k] != null) return a[k];
  }
  return null;
}

function toolOutput(span: Span): unknown {
  const a = span.attributes as Record<string, unknown> | null;
  if (!a) return null;
  for (const k of ["tool.output", "gen_ai.tool.output", "output", "result"]) {
    if (a[k] != null) return a[k];
  }
  return null;
}

function pretty(v: unknown): string {
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
