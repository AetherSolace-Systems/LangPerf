"use client";

import "@xyflow/react/dist/style.css";

import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import type { Span } from "@/lib/api";
import { KIND_GLYPH, KIND_LABEL, kindSwatch } from "@/lib/colors";
import { FlatNodeCompact, type FlatStepData } from "@/components/graph/flat-node-compact";
import { FlatNodeExpanded, type FlatStepExpandedData } from "@/components/graph/flat-node-expanded";
import { GraphToolbar } from "@/components/graph/graph-toolbar";
import { LabelledEdge } from "@/components/graph/labelled-edge";
import { useFullscreen } from "@/components/graph/fullscreen-context";
import { useSelection } from "@/components/selection-context";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { buildSequenceLayout, type LayoutNode } from "@/lib/sequence-layout";
import { extractTotalTokens } from "@/lib/span-fields";
import { buildEdges } from "@/lib/graph-edges";

type FrameData = { layout: LayoutNode; selected: boolean };
type FrameNode = Node<FrameData, "frame">;

function FrameNodeComp({ data }: NodeProps<FrameNode>) {
  const { layout, selected } = data;
  const { frameKind, label, span, nodeKind } = layout;
  const tokens = extractTotalTokens(span);
  const duration = span?.duration_ms ?? null;

  if (frameKind === "parallel") {
    return (
      <>
        <Handle type="target" position={Position.Top} style={{ opacity: 0, pointerEvents: "none" }} />
        <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />
        <div
          className="relative"
          style={{
            width: layout.width,
            height: layout.height,
            border: "1px dashed var(--border-strong)",
            background: "transparent",
            borderRadius: 6,
          }}
        >
          <div
            className="absolute -top-2 left-3 px-1.5 text-[9px] font-mono uppercase tracking-wider"
            style={{ background: "var(--background)", color: "var(--muted)" }}
          >
            ∥ {label}
          </div>
        </div>
      </>
    );
  }

  const swatch = kindSwatch(nodeKind);

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ opacity: 0, pointerEvents: "none" }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />
    <div
      className="relative"
      style={{
        width: layout.width,
        height: layout.height,
        border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
        borderLeft: `3px solid ${swatch.fg}`,
        background: "transparent",
        borderRadius: 6,
      }}
    >
      <div
        className="absolute top-0 left-0 right-0 px-3 flex items-center gap-2 border-b"
        style={{
          height: 30,
          background: "var(--surface-2)",
          borderBottomColor: "var(--border)",
        }}
      >
        <span style={{ color: swatch.fg }} className="text-sm leading-none">
          {KIND_GLYPH[nodeKind] ?? "◆"}
        </span>
        <span
          className="text-[9px] uppercase tracking-wider font-mono"
          style={{ color: swatch.fg }}
        >
          {KIND_LABEL[nodeKind] ?? nodeKind}
        </span>
        <span className="text-sm font-medium text-warm-fog truncate">{label}</span>
        <div className="ml-auto flex items-center gap-3 text-[10px] font-mono tabular-nums text-warm-fog/60">
          {tokens != null ? <span>{fmtTokens(tokens)}t</span> : null}
          {duration != null ? <span>{fmtDuration(duration)}</span> : null}
        </div>
      </div>
    </div>
    </>
  );
}

const nodeTypes = {
  step: FlatNodeCompact,
  stepExpanded: FlatNodeExpanded,
  frame: FrameNodeComp,
};

const edgeTypes = { labelled: LabelledEdge };

export function TrajectoryGraph({ spans }: { spans: Span[] }) {
  const { selectedId, select } = useSelection();
  const { expandAll, expandedIds, toggleExpand } = useFullscreen();
  const rfEdges = useMemo(() => buildEdges(spans), [spans]);
  const { rfNodes } = useMemo(() => {
    const { all } = buildSequenceLayout(spans);
    const nodes: Node[] = all.map((ln) => {
      const isExpanded =
        ln.kind === "step" &&
        !!ln.span &&
        (expandAll || expandedIds.has(ln.span.span_id));

      const type =
        ln.kind === "frame"
          ? "frame"
          : isExpanded
          ? "stepExpanded"
          : "step";

      const height = isExpanded ? 320 : ln.height;

      return {
        id: ln.id,
        type,
        position: { x: ln.x, y: ln.y },
        parentId: ln.parentId ?? undefined,
        extent: ln.parentId ? ("parent" as const) : undefined,
        draggable: false,
        selectable: ln.kind === "step",
        // Compound frame nodes must declare size so children can be positioned
        // relative to them; React Flow reads from style.width/height.
        style: { width: ln.width, height },
        data: ln.kind === "step"
          ? ({
              layout: ln,
              selected: ln.span?.span_id === selectedId,
              commentCount: 0, // wired in Task 6
              onToggle: () => ln.span && toggleExpand(ln.span.span_id),
            } satisfies FlatStepData | FlatStepExpandedData)
          : ({
              layout: ln,
              selected: ln.span?.span_id === selectedId,
            } satisfies FrameData),
        // Frames must render first so children render on top. React Flow
        // respects node order in the array for z-ordering.
        zIndex: ln.kind === "frame"
          ? (ln.frameKind === "parallel" ? 1 : 0)
          : 10,
      };
    });
    // Sort: frames first (by depth ascending), steps last.
    nodes.sort((a, b) => (a.zIndex ?? 0) - (b.zIndex ?? 0));
    return { rfNodes: nodes };
  }, [spans, selectedId, toggleExpand, expandAll, expandedIds]);

  if (rfNodes.length === 0) {
    return <div className="p-6 text-sm text-twilight">No spans to graph.</div>;
  }

  return (
    <div className="w-full h-full bg-midnight relative">
      <GraphToolbar />
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.15}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => {
          const layout = (n.data as FlatStepData | FrameData).layout;
          if (layout.span) select(layout.span);
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
          className="!bg-deep-indigo !border !border-[color:var(--border)] !shadow-none [&_button]:!bg-deep-indigo [&_button]:!border-[color:var(--border)] [&_button]:!text-linen [&_button]:!fill-linen [&_button:hover]:!bg-aether-teal/20"
        />
      </ReactFlow>
    </div>
  );
}
