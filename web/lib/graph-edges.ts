import type { Edge } from "@xyflow/react";
import type { Span } from "./api";
import { kindOf } from "./span-fields";

export type LabelledEdgeData = {
  label: string;
  payload?: string;
};

// Siblings whose time ranges overlap are treated as a parallel group and
// visualised as a fan-out/fan-in (diamond) instead of a sequential chain.
// Must match the tolerance in sequence-layout.ts to stay consistent.
const PARALLEL_TOLERANCE_MS = 60;

function endMs(s: Span): number {
  if (s.ended_at) return new Date(s.ended_at).getTime();
  return new Date(s.started_at).getTime() + (s.duration_ms ?? 0);
}

function groupByParallel(siblings: Span[]): Span[][] {
  if (siblings.length === 0) return [];
  const groups: Span[][] = [];
  let current: Span[] = [siblings[0]];
  let currentEnd = endMs(siblings[0]);
  for (let i = 1; i < siblings.length; i++) {
    const s = siblings[i];
    const startMs = new Date(s.started_at).getTime();
    if (startMs < currentEnd - PARALLEL_TOLERANCE_MS) {
      current.push(s);
      currentEnd = Math.max(currentEnd, endMs(s));
    } else {
      groups.push(current);
      current = [s];
      currentEnd = endMs(s);
    }
  }
  groups.push(current);
  return groups;
}

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
    const groups = groupByParallel(siblings);
    for (let gi = 1; gi < groups.length; gi++) {
      const prev = groups[gi - 1];
      const curr = groups[gi];
      for (const from of prev) {
        for (const to of curr) {
          const label = edgeLabel(from, to, byParent);
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
    }
  }
  return edges;
}

// Walk down from an agent frame to the leaf whose run-time ends last — that
// leaf is "the step that produced the value flowing out."
function exitLeaf(span: Span, byParent: Map<string | null, Span[]>): Span {
  const children = byParent.get(span.span_id) ?? [];
  if (children.length === 0) return span;
  const sorted = [...children].sort((a, b) => endMs(b) - endMs(a));
  return exitLeaf(sorted[0], byParent);
}

function shortName(name: string, max = 28): string {
  if (name.length <= max) return name;
  return name.slice(0, max - 1) + "…";
}

function edgeLabel(
  from: Span,
  to: Span,
  byParent: Map<string | null, Span[]>,
): string {
  const fromKind = kindOf(from);
  const toKind = kindOf(to);
  if (fromKind === "llm" && toKind === "tool") {
    const name = toolName(to) ?? "tool";
    return `tool:${name}`;
  }
  if (fromKind === "tool" && toKind === "llm") return "return";
  if (fromKind === "llm" && toKind === "llm") return "message";
  if (toKind === "agent") return `delegate:${to.name ?? "agent"}`;
  if (fromKind === "agent") {
    const leaf = exitLeaf(from, byParent);
    if (leaf.span_id === from.span_id) return "resume";
    return `resume ← ${shortName(leaf.name)}`;
  }
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
