"use client";

import "@xyflow/react/dist/style.css";

import dagre from "dagre";
import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import type { Span } from "@/lib/api";
import { DRIFT, kindSwatch } from "@/lib/colors";
import { buildEntityGraph, type ActionEdge, type Entity } from "@/lib/entity-graph";
import { fmtDuration, fmtTokens } from "@/lib/format";

type NodeData = {
  entity: Entity;
  selected: boolean;
};

type EntityNode = Node<NodeData, "entity">;

const NODE_WIDTH = 220;
const NODE_HEIGHT = 72;

const kindIcon: Record<Entity["kind"], string> = {
  trajectory: "◆",
  agent: "◇",
  llm: "✦",
  tool: "▸",
  reasoning: "≈",
};

const kindLabel: Record<Entity["kind"], string> = {
  trajectory: "trajectory",
  agent: "agent",
  llm: "llm",
  tool: "tool",
  reasoning: "reasoning",
};

function EntityNodeComp({ data, selected }: NodeProps<EntityNode>) {
  const { entity } = data;
  const swatch = kindSwatch(entity.kind);
  const isActive = selected || data.selected;

  return (
    <div
      className="rounded-full border-2 px-4 py-2 cursor-pointer transition-colors backdrop-blur-sm"
      style={{
        width: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        borderColor: isActive ? DRIFT.marigold : swatch.border,
        background: swatch.bg,
        boxShadow: isActive ? `0 0 0 2px ${DRIFT.marigold}44` : "none",
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={false}
        style={{ background: DRIFT.twilight, borderColor: DRIFT.twilight, width: 6, height: 6 }}
      />
      <div className="flex items-center gap-2">
        <span style={{ color: swatch.fg }} className="text-lg leading-none">
          {kindIcon[entity.kind]}
        </span>
        <div className="min-w-0 flex-1">
          <div
            className="text-[10px] uppercase tracking-wider"
            style={{ color: swatch.fg }}
          >
            {kindLabel[entity.kind]}
            {entity.subtitle ? (
              <span className="text-twilight ml-1">· {entity.subtitle}</span>
            ) : null}
          </div>
          <div
            className="text-sm font-medium text-linen truncate"
            title={entity.label}
          >
            {entity.label}
          </div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={false}
        style={{ background: DRIFT.twilight, borderColor: DRIFT.twilight, width: 6, height: 6 }}
      />
    </div>
  );
}

const nodeTypes = { entity: EntityNodeComp };

function layout(
  nodes: EntityNode[],
  edges: Edge[],
): { nodes: EntityNode[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: "TB",
    nodesep: 44,
    ranksep: 90,
    marginx: 20,
    marginy: 20,
  });

  for (const n of nodes) {
    g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const e of edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);

  const positioned = nodes.map((n) => {
    const pos = g.node(n.id);
    return {
      ...n,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });
  return { nodes: positioned, edges };
}

function edgeLabel(e: ActionEdge): string {
  const count = e.callCount === 1 ? "1 call" : `${e.callCount} calls`;
  const parts = [`${e.action} · ${count}`];
  if (e.totalTokens > 0) parts.push(fmtTokens(e.totalTokens) + "t");
  if (e.totalDurationMs > 0) parts.push(fmtDuration(e.totalDurationMs));
  return parts.join(" · ");
}

type EdgePayload = { actionEdge: ActionEdge };

export function TrajectoryGraph({
  spans,
  selectedId,
  onSelect,
}: {
  spans: Span[];
  selectedId: string | null;
  onSelect: (span: Span) => void;
}) {
  const { entities, edges } = useMemo(
    () => buildEntityGraph(spans),
    [spans],
  );

  const { nodes, rfEdges, edgePayload } = useMemo(() => {
    const selectedSpan = selectedId
      ? spans.find((s) => s.span_id === selectedId) ?? null
      : null;

    const nodesRaw: EntityNode[] = entities.map((e) => ({
      id: e.id,
      type: "entity",
      position: { x: 0, y: 0 },
      data: {
        entity: e,
        selected: selectedSpan
          ? e.spans.some((s) => s.span_id === selectedSpan.span_id)
          : false,
      },
    }));

    const rfEdgesRaw: Edge[] = edges.map((e) => {
      const isActive = selectedSpan
        ? e.spans.some((s) => s.span_id === selectedSpan.span_id)
        : false;
      const swatchHex =
        e.action === "chat"
          ? DRIFT.driftViolet
          : e.action === "invoke"
            ? DRIFT.marigold
            : e.action === "think"
              ? DRIFT.plum
              : DRIFT.lagoon;
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: edgeLabel(e),
        labelStyle: {
          fill: DRIFT.linen,
          fontSize: 10,
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        },
        labelBgStyle: {
          fill: DRIFT.deepIndigo,
          fillOpacity: 0.92,
        },
        labelBgPadding: [6, 3],
        labelBgBorderRadius: 4,
        type: "smoothstep",
        animated: isActive,
        style: {
          stroke: isActive ? DRIFT.marigold : swatchHex,
          strokeWidth: isActive ? 2 : 1.4,
          strokeOpacity: isActive ? 1 : 0.7,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 18,
          height: 18,
          color: isActive ? DRIFT.marigold : swatchHex,
        },
      };
    });

    const laidOut = layout(nodesRaw, rfEdgesRaw);
    const payloadMap: Record<string, EdgePayload> = {};
    for (const e of edges) payloadMap[e.id] = { actionEdge: e };
    return {
      nodes: laidOut.nodes,
      rfEdges: laidOut.edges,
      edgePayload: payloadMap,
    };
  }, [entities, edges, selectedId, spans]);

  if (entities.length === 0) {
    return <div className="p-6 text-sm text-twilight">No entities to graph.</div>;
  }

  const handleNodeClick = (entity: Entity) => {
    if (entity.spans.length > 0) {
      onSelect(entity.spans[0]);
    }
  };

  const handleEdgeClick = (edgeId: string) => {
    const payload = edgePayload[edgeId];
    if (!payload) return;
    const spans = payload.actionEdge.spans;
    if (spans.length === 0) return;
    // Cycle through spans if the selected one is already in this edge,
    // else pick the first.
    const currentIdx = spans.findIndex((s) => s.span_id === selectedId);
    const next = spans[(currentIdx + 1) % spans.length];
    onSelect(next);
  };

  return (
    <div className="w-full h-full bg-midnight">
      <ReactFlow
        nodes={nodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => handleNodeClick((n.data as NodeData).entity)}
        onEdgeClick={(_, e) => handleEdgeClick(e.id)}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        panOnDrag={true}
        zoomOnScroll={true}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={16}
          size={1}
          color="rgba(139,140,199,0.08)"
        />
        <Controls
          showInteractive={false}
          className="!bg-deep-indigo !border !border-[color:var(--border)] !shadow-none [&_button]:!bg-deep-indigo [&_button]:!border-[color:var(--border)] [&_button]:!text-linen [&_button]:!fill-linen [&_button:hover]:!bg-drift-violet/20"
        />
      </ReactFlow>
    </div>
  );
}
