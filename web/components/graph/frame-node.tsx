"use client";

import {
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import { KIND_GLYPH, KIND_LABEL, kindSwatch } from "@/lib/colors";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { type LayoutNode } from "@/lib/sequence-layout";
import { extractTotalTokens } from "@/lib/span-fields";

export type FrameData = { layout: LayoutNode; selected: boolean };
export type FrameNode = Node<FrameData, "frame">;

export function FrameNodeComp({ data }: NodeProps<FrameNode>) {
  const { layout, selected } = data;
  const { frameKind, label, span, nodeKind } = layout;
  const tokens = extractTotalTokens(span);
  const duration = span?.duration_ms ?? null;

  if (frameKind === "parallel") {
    return (
      <>
        <Handle id="t-tl" type="target" position={Position.Left} style={{ top: 10, opacity: 0, pointerEvents: "none" }} />
        <Handle id="s-br" type="source" position={Position.Right} style={{ top: "calc(100% - 10px)", opacity: 0, pointerEvents: "none" }} />
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
      <Handle id="t-tl" type="target" position={Position.Left} style={{ top: 10, opacity: 0, pointerEvents: "none" }} />
      <Handle id="s-br" type="source" position={Position.Right} style={{ top: "calc(100% - 10px)", opacity: 0, pointerEvents: "none" }} />
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
