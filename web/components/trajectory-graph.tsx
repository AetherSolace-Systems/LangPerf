"use client";

import "@xyflow/react/dist/style.css";

import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import type { Span } from "@/lib/api";
import { DRIFT, KIND_GLYPH, KIND_LABEL, kindSwatch } from "@/lib/colors";
import { useSelection } from "@/components/selection-context";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { buildSequenceLayout, type LayoutNode } from "@/lib/sequence-layout";
import { extractTotalTokens } from "@/lib/span-fields";

type StepData = { layout: LayoutNode; selected: boolean };
type FrameData = { layout: LayoutNode; selected: boolean };

type StepNode = Node<StepData, "step">;
type FrameNode = Node<FrameData, "frame">;

function StepNodeComp({ data }: NodeProps<StepNode>) {
  const { layout, selected } = data;
  const { span, nodeKind, execOrder } = layout;
  const swatch = kindSwatch(nodeKind);
  const tokens = extractTotalTokens(span);
  const isError = span?.status_code === "ERROR";

  // LLM calls are pills; everything else is a rounded rect.
  const radius = nodeKind === "llm" ? 999 : 10;

  return (
    <div
      className="relative transition-colors cursor-pointer"
      style={{
        width: layout.width,
        height: layout.height,
        borderRadius: radius,
        border: `2px solid ${selected ? DRIFT.marigold : swatch.border}`,
        background: "var(--surface)",
        boxShadow: selected ? `0 0 0 2px ${DRIFT.marigold}44` : undefined,
      }}
    >
      <div className="h-full px-3 py-2 flex items-center gap-2.5">
        {execOrder ? (
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono tabular-nums font-semibold flex-shrink-0"
            style={{ background: DRIFT.marigold, color: DRIFT.midnight }}
          >
            {execOrder}
          </div>
        ) : null}
        <div className="min-w-0 flex-1">
          <div
            className="text-[9px] uppercase tracking-wider font-mono flex items-center gap-1"
            style={{ color: swatch.fg }}
          >
            <span>{KIND_GLYPH[nodeKind] ?? "•"}</span>
            <span>{KIND_LABEL[nodeKind] ?? nodeKind}</span>
          </div>
          <div className="text-[12px] font-medium text-linen truncate mt-0.5">
            {layout.label}
          </div>
        </div>
        <div className="flex flex-col items-end text-[9px] font-mono tabular-nums text-twilight flex-shrink-0">
          {tokens != null ? <div>{fmtTokens(tokens)}t</div> : null}
          <div>{fmtDuration(span?.duration_ms ?? null)}</div>
        </div>
        {isError ? (
          <span className="absolute -top-1 -right-1 text-coral text-sm">!</span>
        ) : null}
      </div>
    </div>
  );
}

function FrameNodeComp({ data }: NodeProps<FrameNode>) {
  const { layout, selected } = data;
  const { frameKind, label, span, nodeKind } = layout;

  const tokens = extractTotalTokens(span);
  const duration = span?.duration_ms ?? null;

  if (frameKind === "parallel") {
    return (
      <div
        className="relative"
        style={{
          width: layout.width,
          height: layout.height,
          borderRadius: 10,
          border: `1.5px dashed ${DRIFT.twilight}`,
          background: "rgba(31,32,53,0.35)",
        }}
      >
        <div
          className="absolute -top-2.5 left-4 px-2 text-[9px] font-mono uppercase tracking-wider"
          style={{ background: DRIFT.midnight, color: DRIFT.twilight }}
        >
          ∥ {label}
        </div>
      </div>
    );
  }

  // agent / trajectory / generic container
  const swatch = kindSwatch(nodeKind);
  const borderColor = selected ? DRIFT.marigold : swatch.border;
  const titleBg = `linear-gradient(to bottom, ${swatch.bg}, transparent)`;

  return (
    <div
      className="relative"
      style={{
        width: layout.width,
        height: layout.height,
        borderRadius: 12,
        border: `2px solid ${borderColor}`,
        background: "rgba(20,20,31,0.55)",
      }}
    >
      <div
        className="absolute top-0 left-0 right-0 rounded-t-[10px] border-b px-3 flex items-center gap-2"
        style={{
          height: 34,
          background: titleBg,
          borderColor: swatch.border,
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
        <span className="text-sm font-medium text-linen truncate">{label}</span>
        <div className="ml-auto flex items-center gap-3 text-[10px] font-mono tabular-nums text-twilight">
          {tokens != null ? <span>{fmtTokens(tokens)}t</span> : null}
          {duration != null ? <span>{fmtDuration(duration)}</span> : null}
        </div>
      </div>
    </div>
  );
}

const nodeTypes = {
  step: StepNodeComp,
  frame: FrameNodeComp,
};

export function TrajectoryGraph({ spans }: { spans: Span[] }) {
  const { selectedId, select } = useSelection();
  const { rfNodes } = useMemo(() => {
    const { all } = buildSequenceLayout(spans);
    const nodes: Node[] = all.map((ln) => ({
      id: ln.id,
      type: ln.kind, // "step" | "frame"
      position: { x: ln.x, y: ln.y },
      parentId: ln.parentId ?? undefined,
      extent: ln.parentId ? "parent" : undefined,
      draggable: false,
      selectable: ln.kind === "step",
      // Compound frame nodes must declare size so children can be positioned
      // relative to them; React Flow reads from style.width/height.
      style: { width: ln.width, height: ln.height },
      data: {
        layout: ln,
        selected: ln.span?.span_id === selectedId,
      } satisfies StepData | FrameData,
      // Frames must render first so children render on top. React Flow
      // respects node order in the array for z-ordering.
      zIndex: ln.kind === "frame"
        ? (ln.frameKind === "parallel" ? 1 : 0)
        : 10,
    }));
    // Sort: frames first (by depth ascending), steps last.
    nodes.sort((a, b) => (a.zIndex ?? 0) - (b.zIndex ?? 0));
    return { rfNodes: nodes };
  }, [spans, selectedId]);

  if (rfNodes.length === 0) {
    return <div className="p-6 text-sm text-twilight">No spans to graph.</div>;
  }

  return (
    <div className="w-full h-full bg-midnight">
      <ReactFlow
        nodes={rfNodes}
        edges={[]}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.15}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, n) => {
          const layout = (n.data as StepData | FrameData).layout;
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
