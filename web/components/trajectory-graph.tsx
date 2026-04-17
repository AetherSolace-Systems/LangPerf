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

const kindColors: Record<string, { text: string; border: string; bg: string }> = {
  llm: {
    text: "text-emerald-300",
    border: "border-emerald-500/40",
    bg: "bg-emerald-500/5",
  },
  tool: {
    text: "text-violet-300",
    border: "border-violet-500/40",
    bg: "bg-violet-500/5",
  },
  tool_call: {
    text: "text-violet-300",
    border: "border-violet-500/40",
    bg: "bg-violet-500/5",
  },
  agent: {
    text: "text-sky-300",
    border: "border-sky-500/40",
    bg: "bg-sky-500/5",
  },
  chain: {
    text: "text-amber-300",
    border: "border-amber-500/40",
    bg: "bg-amber-500/5",
  },
  retriever: {
    text: "text-orange-300",
    border: "border-orange-500/40",
    bg: "bg-orange-500/5",
  },
  embedding: {
    text: "text-pink-300",
    border: "border-pink-500/40",
    bg: "bg-pink-500/5",
  },
  reasoning: {
    text: "text-teal-300",
    border: "border-teal-500/40",
    bg: "bg-teal-500/5",
  },
  trajectory: {
    text: "text-white",
    border: "border-white/40",
    bg: "bg-white/5",
  },
};

function colorsFor(kind: string) {
  return (
    kindColors[kind] ?? {
      text: "text-[var(--muted)]",
      border: "border-[var(--border)]",
      bg: "bg-white/[0.02]",
    }
  );
}

function TrajectoryNodeComp({ data, selected }: NodeProps<TrajectoryNode>) {
  const { span, kind } = data;
  const colors = colorsFor(kind);

  const tokens =
    (span.attributes["llm.token_count.total"] as number | undefined) ??
    (span.attributes["gen_ai.usage.total_tokens"] as number | undefined) ??
    null;
  const isError = span.status_code === "ERROR";
  const isActive = selected || data.selected;

  return (
    <div
      className={`rounded-md border-2 ${
        isActive
          ? "border-[var(--accent)] shadow-[0_0_0_2px_rgba(91,140,255,0.2)]"
          : colors.border
      } ${colors.bg} backdrop-blur-sm px-3 py-2 cursor-pointer transition-colors`}
      style={{ width: NODE_WIDTH, minHeight: NODE_HEIGHT }}
    >
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={false}
        className="!bg-[var(--border)] !border-[var(--border)] !w-1.5 !h-1.5"
      />
      <div
        className={`text-[10px] font-mono uppercase tracking-wider ${colors.text}`}
      >
        {kind}
        {isError ? (
          <span className="ml-2 text-rose-400">!</span>
        ) : null}
      </div>
      <div className="mt-0.5 text-sm font-medium text-[var(--foreground)] truncate">
        {span.name}
      </div>
      <div className="mt-1 flex items-center gap-3 text-[10px] text-[var(--muted)] font-mono tabular-nums">
        {tokens != null ? <span>{fmtTokens(tokens)}t</span> : null}
        <span>{fmtDuration(span.duration_ms)}</span>
        {span.notes ? (
          <span
            className="text-[var(--accent)]"
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
        className="!bg-[var(--border)] !border-[var(--border)] !w-1.5 !h-1.5"
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
        style: {
          stroke: "rgba(255,255,255,0.18)",
          strokeWidth: 1.25,
        },
      }));
    return layout(rawNodes, rawEdges);
  }, [spans, selectedId]);

  if (spans.length === 0) {
    return (
      <div className="p-6 text-sm text-[var(--muted)]">
        No spans to graph.
      </div>
    );
  }

  return (
    <div className="w-full h-full">
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
          color="rgba(255,255,255,0.06)"
        />
        <Controls
          showInteractive={false}
          className="!bg-[var(--background)] !border !border-[var(--border)] !shadow-none [&_button]:!bg-[var(--background)] [&_button]:!border-[var(--border)] [&_button]:!text-[var(--foreground)] [&_button:hover]:!bg-white/10"
        />
        <MiniMap
          className="!bg-[var(--background)] !border !border-[var(--border)]"
          maskColor="rgba(0,0,0,0.6)"
          nodeColor={(n) => {
            const c = colorsFor((n.data as NodeData).kind);
            // Strip Tailwind class name to rough color (approximate).
            if (c.text.includes("emerald")) return "#34d399";
            if (c.text.includes("violet")) return "#a78bfa";
            if (c.text.includes("sky")) return "#7dd3fc";
            if (c.text.includes("amber")) return "#fbbf24";
            if (c.text.includes("orange")) return "#fb923c";
            if (c.text.includes("pink")) return "#f472b6";
            if (c.text.includes("teal")) return "#2dd4bf";
            if (c.text.includes("white")) return "#ffffff";
            return "#64748b";
          }}
          nodeStrokeWidth={0}
        />
      </ReactFlow>
    </div>
  );
}
