"use client";

import "@xyflow/react/dist/style.css";

import dagre from "dagre";
import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import type { Span } from "@/lib/api";
import { DRIFT, kindSwatch } from "@/lib/colors";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { kindOf } from "@/lib/span-fields";

type NodeData = {
  span: Span;
  kind: string;
  selected: boolean;
};

type TrajectoryNode = Node<NodeData, "trajectory">;

const NODE_WIDTH = 260;
const NODE_HEIGHT = 96;

function TrajectoryNodeComp({ data, selected }: NodeProps<TrajectoryNode>) {
  const { span, kind } = data;
  const swatch = kindSwatch(kind);

  const tokens =
    (span.attributes["llm.token_count.total"] as number | undefined) ??
    (span.attributes["gen_ai.usage.total_tokens"] as number | undefined) ??
    null;
  const isError = span.status_code === "ERROR";
  const isActive = selected || data.selected;

  return (
    <div
      className="rounded-md border-2 backdrop-blur-sm px-3 py-2 cursor-pointer transition-colors"
      style={{
        width: NODE_WIDTH,
        minHeight: NODE_HEIGHT,
        borderColor: isActive ? DRIFT.marigold : swatch.border,
        background: swatch.bg,
        boxShadow: isActive ? `0 0 0 2px ${DRIFT.marigold}33` : "none",
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={false}
        style={{ background: DRIFT.twilight, borderColor: DRIFT.twilight, width: 6, height: 6 }}
      />
      <div
        className="text-[10px] font-mono uppercase tracking-wider"
        style={{ color: swatch.fg }}
      >
        {kind}
        {isError ? <span className="ml-2 text-coral">!</span> : null}
      </div>
      <div className="mt-0.5 text-sm font-medium text-linen truncate">
        {span.name}
      </div>
      <div className="mt-1 flex items-center gap-3 text-[10px] text-twilight font-mono tabular-nums">
        {tokens != null ? <span>{fmtTokens(tokens)}t</span> : null}
        <span>{fmtDuration(span.duration_ms)}</span>
        {span.notes ? (
          <span
            style={{ color: DRIFT.marigold }}
            title="has notes"
            aria-label="has notes"
          >
            ●
          </span>
        ) : null}
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

const nodeTypes = { trajectory: TrajectoryNodeComp };

function layout(
  nodes: TrajectoryNode[],
  edges: Edge[],
): { nodes: TrajectoryNode[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: "TB",
    nodesep: 30,
    ranksep: 40,
    marginx: 12,
    marginy: 12,
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
      position: {
        x: pos.x - NODE_WIDTH / 2,
        y: pos.y - NODE_HEIGHT / 2,
      },
    };
  });

  return { nodes: positioned, edges };
}

export function TrajectoryGraph({
  spans,
  selectedId,
  onSelect,
}: {
  spans: Span[];
  selectedId: string | null;
  onSelect: (span: Span) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const spanById = new Map(spans.map((s) => [s.span_id, s]));
    const rawNodes: TrajectoryNode[] = spans.map((s) => ({
      id: s.span_id,
      type: "trajectory",
      position: { x: 0, y: 0 },
      data: {
        span: s,
        kind: kindOf(s),
        selected: s.span_id === selectedId,
      },
    }));
    const rawEdges: Edge[] = spans
      .filter((s) => s.parent_span_id && spanById.has(s.parent_span_id))
      .map((s) => ({
        id: `${s.parent_span_id}->${s.span_id}`,
        source: s.parent_span_id!,
        target: s.span_id,
        type: "smoothstep",
        animated: false,
        style: { stroke: DRIFT.twilight, strokeOpacity: 0.6, strokeWidth: 1.25 },
      }));
    return layout(rawNodes, rawEdges);
  }, [spans, selectedId]);

  if (spans.length === 0) {
    return <div className="p-6 text-sm text-twilight">No spans to graph.</div>;
  }

  return (
    <div className="w-full h-full bg-midnight">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        minZoom={0.2}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => {
          const span = (n.data as NodeData).span;
          onSelect(span);
        }}
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
        <MiniMap
          className="!bg-deep-indigo !border !border-[color:var(--border)]"
          maskColor="rgba(20,20,31,0.6)"
          nodeColor={(n) => kindSwatch((n.data as NodeData).kind).solid}
          nodeStrokeWidth={0}
        />
      </ReactFlow>
    </div>
  );
}
