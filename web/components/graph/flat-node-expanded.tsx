"use client";

import type { NodeProps, Node } from "@xyflow/react";
import { Handle, Position } from "@xyflow/react";
import type { LayoutNode } from "@/lib/sequence-layout";
import { KIND_GLYPH, KIND_LABEL, kindSwatch } from "@/lib/colors";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { extractTotalTokens, kindOf } from "@/lib/span-fields";
import { ExpandedToolBody } from "./expanded-tool-body";
import { ExpandedLlmBody } from "./expanded-llm-body";

export type FlatStepExpandedData = {
  layout: LayoutNode;
  selected: boolean;
  commentCount: number;
  onToggle: () => void;
};
type ExpandedNode = Node<FlatStepExpandedData, "stepExpanded">;

export function FlatNodeExpanded({ data }: NodeProps<ExpandedNode>) {
  const { layout, selected, commentCount, onToggle } = data;
  const { span, nodeKind } = layout;
  if (!span) return null;
  const swatch = kindSwatch(nodeKind);
  const kind = kindOf(span);
  const tokens = extractTotalTokens(span);
  const isError = span.status_code === "ERROR";

  return (
    <div
      data-node-kind={nodeKind}
      data-selected={selected ? "true" : "false"}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      className="relative cursor-pointer flex flex-col"
      style={{
        width: layout.width,
        height: 320,
        background: "var(--surface)",
        border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
        borderLeft: `3px solid ${isError ? "var(--warn)" : swatch.fg}`,
        borderRadius: 6,
        boxShadow: selected ? "0 0 0 2px rgba(107,186,177,0.25)" : "none",
        overflow: "hidden",
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0, pointerEvents: "none" }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0, pointerEvents: "none" }} />
      <div
        className="px-3 py-2 flex items-center gap-2 border-b flex-shrink-0"
        style={{ borderBottomColor: "var(--border)" }}
      >
        <div
          className="text-[9px] uppercase tracking-wider font-mono flex items-center gap-1"
          style={{ color: swatch.fg }}
        >
          <span>{KIND_GLYPH[nodeKind] ?? "•"}</span>
          <span>{KIND_LABEL[nodeKind] ?? nodeKind}</span>
        </div>
        <span className="text-[12px] font-medium text-warm-fog truncate flex-1">
          {layout.label}
        </span>
        <span className="flex items-center gap-2 text-[9px] font-mono tabular-nums text-warm-fog/60 flex-shrink-0">
          {tokens != null ? <span>{fmtTokens(tokens)}t</span> : null}
          <span>{fmtDuration(span.duration_ms ?? null)}</span>
        </span>
        {isError ? <span className="text-warn text-sm ml-1">!</span> : null}
        {commentCount > 0 ? (
          <span className="min-w-[16px] h-[16px] px-1 rounded-full bg-peach-neon text-carbon text-[9px] font-bold flex items-center justify-center">
            {commentCount}
          </span>
        ) : null}
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {kind === "llm" ? <ExpandedLlmBody span={span} /> : null}
        {kind === "tool" ? <ExpandedToolBody span={span} /> : null}
        {kind !== "llm" && kind !== "tool" ? (
          <pre
            data-expanded-body
            className="font-mono text-[10px] text-warm-fog/70 whitespace-pre-wrap break-words"
          >
            {JSON.stringify(span.attributes, null, 2).slice(0, 400)}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
