"use client";

import "@xyflow/react/dist/style.css";

import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type Node,
} from "@xyflow/react";

import type { Span } from "@/lib/api";
import { FlatNodeCompact, type FlatStepData } from "@/components/graph/flat-node-compact";
import { FlatNodeExpanded, type FlatStepExpandedData } from "@/components/graph/flat-node-expanded";
import { FrameNodeComp, type FrameData } from "@/components/graph/frame-node";
import { GraphToolbar } from "@/components/graph/graph-toolbar";
import { LabelledEdge } from "@/components/graph/labelled-edge";
import { useFullscreen } from "@/components/graph/fullscreen-context";
import { useSelection } from "@/components/selection-context";
import { buildSequenceLayout } from "@/lib/sequence-layout";
import { buildEdges } from "@/lib/graph-edges";
import { FloatingInspector } from "@/components/graph/floating-inspector";

const nodeTypes = {
  step: FlatNodeCompact,
  stepExpanded: FlatNodeExpanded,
  frame: FrameNodeComp,
};

const edgeTypes = { labelled: LabelledEdge };

export function TrajectoryGraph({
  spans,
  commentCounts,
}: {
  spans: Span[];
  commentCounts?: Map<string, number>;
}) {
  const { selectedId, select } = useSelection();
  const { expandAll, expandedIds, toggleExpand, fsOpen } = useFullscreen();
  const rfEdges = useMemo(() => buildEdges(spans), [spans]);
  const { rfNodes } = useMemo(() => {
    // Pass expand state into layout so heights reflect the rendered size and
    // nodes don't overlap.
    const { all } = buildSequenceLayout(spans, { expandedIds, expandAll });
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
        style: { width: ln.width, height: ln.height },
        data: ln.kind === "step"
          ? ({
              layout: ln,
              selected: ln.span?.span_id === selectedId,
              commentCount: ln.span ? commentCounts?.get(ln.span.span_id) ?? 0 : 0,
              onToggle: () => ln.span && toggleExpand(ln.span.span_id),
              onSelect: () => ln.span && select(ln.span),
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
  }, [spans, selectedId, toggleExpand, expandAll, expandedIds, commentCounts]);

  if (rfNodes.length === 0) {
    return <div className="p-6 text-sm text-patina">No spans to graph.</div>;
  }

  return (
    <div className="w-full h-full bg-carbon relative">
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
          className="!bg-steel-mist !border !border-[color:var(--border)] !shadow-none [&_button]:!bg-steel-mist [&_button]:!border-[color:var(--border)] [&_button]:!text-warm-fog [&_button]:!fill-warm-fog [&_button:hover]:!bg-aether-teal/20"
        />
      </ReactFlow>
      {fsOpen ? (
        <FloatingInspector onOpenFull={() => { /* v1: no-op. v-next: drive sidebar open + tab=detail. */ }} />
      ) : null}
    </div>
  );
}
