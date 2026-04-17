/**
 * Collapse a flat list of spans into an entity-relationship graph.
 *
 *   - Nodes are the distinct **objects** involved in a trajectory:
 *       • the trajectory root (entry)
 *       • each agent (by name)
 *       • each distinct LLM (by system + model)
 *       • each distinct tool (by name)
 *
 *   - Edges are the **actions** between them: "agent X called LLM Y three times,
 *     total 342 tokens, 1.2s combined." Multiple calls between the same pair
 *     aggregate into one edge with a count.
 *
 * Reasoning/generic spans are attributed back to their nearest agent (no edge
 * is emitted for them in this view — the timeline covers temporal order).
 */

import type { Span } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";

export type EntityKind = "trajectory" | "agent" | "llm" | "tool" | "reasoning";

export type Entity = {
  id: string;
  kind: EntityKind;
  label: string;
  subtitle?: string;
  spans: Span[]; // spans where this entity is the primary referent
};

export type ActionEdge = {
  id: string;
  source: string;
  target: string;
  action: "dispatch" | "chat" | "invoke" | "think";
  spans: Span[]; // all spans collapsed into this edge, ordered by started_at
  callCount: number;
  totalTokens: number;
  totalDurationMs: number;
};

export function buildEntityGraph(
  spans: Span[],
): { entities: Entity[]; edges: ActionEdge[] } {
  if (spans.length === 0) return { entities: [], edges: [] };

  const byId = new Map<string, Span>(spans.map((s) => [s.span_id, s]));

  // Root entity = the trajectory span (if present) or a synthetic "root"
  const trajectorySpan =
    spans.find((s) => kindOf(s) === "trajectory") ??
    // fallback: the span with no parent or with a parent outside our set
    spans.find((s) => !s.parent_span_id || !byId.has(s.parent_span_id));
  const rootEntity: Entity = trajectorySpan
    ? {
        id: "trajectory:" + trajectorySpan.span_id,
        kind: "trajectory",
        label:
          (trajectorySpan.attributes["langperf.trajectory.name"] as string) ??
          trajectorySpan.name ??
          "trajectory",
        spans: [trajectorySpan],
      }
    : { id: "root", kind: "trajectory", label: "root", spans: [] };

  const entities = new Map<string, Entity>();
  entities.set(rootEntity.id, rootEntity);

  const edges = new Map<string, ActionEdge>();

  for (const span of spans) {
    const kind = kindOf(span);

    // Skip the trajectory root — it IS the entity, not a call.
    if (span === trajectorySpan) continue;

    // Find the actor: nearest ancestor agent, or the root.
    const actor = resolveActor(span, byId, rootEntity);

    const target = resolveTarget(span, kind, actor);
    if (!target) continue; // generic spans: no edge (parent agent owns them)

    upsertEntity(entities, actor);
    upsertEntity(entities, target);

    const edgeId = `${actor.id}\u2192${target.id}`;
    let edge = edges.get(edgeId);
    if (!edge) {
      edge = {
        id: edgeId,
        source: actor.id,
        target: target.id,
        action: actionFor(target.kind),
        spans: [],
        callCount: 0,
        totalTokens: 0,
        totalDurationMs: 0,
      };
      edges.set(edgeId, edge);
    }
    edge.spans.push(span);
    edge.callCount += 1;
    edge.totalTokens += extractTokens(span);
    edge.totalDurationMs += span.duration_ms ?? 0;

    // Attach this span to the target entity too (so clicking the node gives a usage).
    const t = entities.get(target.id);
    if (t) t.spans.push(span);
  }

  // Sort each edge's spans chronologically and dedupe entity spans.
  for (const e of edges.values()) {
    e.spans.sort((a, b) =>
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
    );
  }
  for (const ent of entities.values()) {
    ent.spans.sort((a, b) =>
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
    );
  }

  return {
    entities: Array.from(entities.values()),
    edges: Array.from(edges.values()),
  };
}

function upsertEntity(map: Map<string, Entity>, e: Entity) {
  const existing = map.get(e.id);
  if (existing) {
    // Keep earlier-registered entity's spans; we only need identity here.
    return;
  }
  map.set(e.id, { ...e, spans: [...e.spans] });
}

function resolveActor(
  span: Span,
  byId: Map<string, Span>,
  root: Entity,
): Entity {
  // Walk up until we hit an agent span (or run out of ancestors → root).
  let cur = span.parent_span_id ? byId.get(span.parent_span_id) : undefined;
  while (cur) {
    const k = kindOf(cur);
    if (k === "agent") {
      const name =
        (cur.attributes["langperf.node.name"] as string) ?? cur.name;
      return {
        id: `agent:${name}`,
        kind: "agent",
        label: name,
        spans: [cur],
      };
    }
    if (k === "trajectory") return root;
    cur = cur.parent_span_id ? byId.get(cur.parent_span_id) : undefined;
  }
  return root;
}

function resolveTarget(span: Span, kind: string, actor: Entity): Entity | null {
  if (kind === "llm") {
    const model = (span.attributes["llm.model_name"] as string) ??
      (span.attributes["gen_ai.request.model"] as string) ??
      "unknown-model";
    const system = (span.attributes["llm.system"] as string) ??
      (span.attributes["gen_ai.system"] as string) ??
      "";
    const id = system ? `llm:${system}:${model}` : `llm:${model}`;
    return {
      id,
      kind: "llm",
      label: model,
      subtitle: system || undefined,
      spans: [],
    };
  }
  if (kind === "tool" || kind === "tool_call") {
    const name = (span.attributes["tool.name"] as string) ??
      (span.attributes["langperf.node.name"] as string) ??
      span.name;
    return {
      id: `tool:${name}`,
      kind: "tool",
      label: name,
      spans: [],
    };
  }
  if (kind === "agent") {
    const name = (span.attributes["langperf.node.name"] as string) ?? span.name;
    return {
      id: `agent:${name}`,
      kind: "agent",
      label: name,
      spans: [span],
    };
  }
  if (kind === "reasoning") {
    // One reasoning entity per actor — "the thinking this actor did" — so
    // multiple reasoning spans from the same actor collapse into one node
    // with a high call count, and multiple actors each get their own.
    return {
      id: `reasoning:${actor.id}`,
      kind: "reasoning",
      label: "reasoning",
      subtitle: actor.kind === "trajectory" ? undefined : `in ${actor.label}`,
      spans: [],
    };
  }
  return null;
}

function actionFor(kind: EntityKind): ActionEdge["action"] {
  if (kind === "agent") return "dispatch";
  if (kind === "llm") return "chat";
  if (kind === "tool") return "invoke";
  if (kind === "reasoning") return "think";
  return "dispatch";
}

function extractTokens(span: Span): number {
  return (
    (span.attributes["llm.token_count.total"] as number | undefined) ??
    (span.attributes["gen_ai.usage.total_tokens"] as number | undefined) ??
    0
  );
}
