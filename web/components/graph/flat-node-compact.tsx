"use client";

import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import type { LayoutNode } from "@/lib/sequence-layout";
import { KIND_GLYPH, KIND_LABEL, kindSwatch } from "@/lib/colors";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { extractTotalTokens } from "@/lib/span-fields";

export type FlatStepData = {
  layout: LayoutNode;
  selected: boolean;
  commentCount: number;
  onToggle: () => void;
  onSelect: () => void;
};
type FlatStepNode = Node<FlatStepData, "step">;

export function FlatNodeCompact({ data }: NodeProps<FlatStepNode>) {
  const { layout, selected, commentCount, onToggle, onSelect } = data;
  const { span, nodeKind, execOrder } = layout;
  const swatch = kindSwatch(nodeKind);
  const tokens = extractTotalTokens(span);
  const isError = span?.status_code === "ERROR";

  return (
    <>
      <Handle id="t-top" type="target" position={Position.Top} style={{ opacity: 0, pointerEvents: "none" }} />
      <Handle id="t-left" type="target" position={Position.Left} style={{ opacity: 0, pointerEvents: "none" }} />
      <Handle id="s-bottom" type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }} />
      <Handle id="s-right" type="source" position={Position.Right} style={{ opacity: 0, pointerEvents: "none" }} />
    <div
      data-node-kind={nodeKind}
      data-selected={selected ? "true" : "false"}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      className="relative cursor-pointer transition-colors"
      style={{
        width: layout.width,
        height: layout.height,
        background: "var(--surface)",
        border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
        borderLeft: `3px solid ${isError ? "var(--warn)" : swatch.fg}`,
        borderRadius: 6,
        boxShadow: selected ? "0 0 0 2px rgba(107,186,177,0.25)" : "none",
      }}
    >
      <div className="h-full px-3 py-2 flex items-center gap-2.5">
        {execOrder ? (
          <div
            className="w-5 h-5 rounded flex items-center justify-center text-[10px] font-mono tabular-nums flex-shrink-0"
            style={{ background: "var(--surface-2)", color: "var(--muted)" }}
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
          <div className="text-[12px] font-medium text-warm-fog truncate mt-0.5">
            {layout.label}
          </div>
        </div>
        <div className="flex flex-col items-end text-[9px] font-mono tabular-nums text-warm-fog/60 flex-shrink-0">
          {tokens != null ? <div>{fmtTokens(tokens)}t</div> : null}
          <div>{fmtDuration(span?.duration_ms ?? null)}</div>
        </div>
        <button
          type="button"
          title="Expand body"
          aria-label="Expand"
          onClick={(e) => {
            e.stopPropagation();
            onSelect();
            onToggle();
          }}
          className="flex-shrink-0 w-5 h-5 flex items-center justify-center text-[10px] text-warm-fog/50 hover:text-aether-teal rounded hover:bg-warm-fog/5"
        >
          ▸
        </button>
        {isError ? (
          <span className="absolute -top-1 -right-1 text-warn text-sm">!</span>
        ) : null}
        {commentCount > 0 ? (
          <span
            className="absolute -top-1.5 -right-1.5 min-w-[16px] h-[16px] px-1 rounded-full bg-peach-neon text-carbon text-[9px] font-bold flex items-center justify-center"
            aria-label={`${commentCount} comment${commentCount === 1 ? "" : "s"}`}
          >
            {commentCount}
          </span>
        ) : null}
      </div>
    </div>
    </>
  );
}
