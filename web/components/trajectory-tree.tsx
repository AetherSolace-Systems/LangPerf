"use client";

import { useMemo, useState } from "react";
import type { Span } from "@/lib/api";
import { kindSwatch } from "@/lib/colors";
import { useSelection } from "@/components/selection-context";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { extractTotalTokens, kindOf } from "@/lib/span-fields";
import { buildTree, type TreeNode } from "@/lib/tree";

export function TrajectoryTree({ spans }: { spans: Span[] }) {
  const roots = useMemo(() => buildTree(spans), [spans]);
  return (
    <div className="text-sm font-mono">
      {roots.length === 0 ? (
        <div className="p-5 text-twilight">No spans.</div>
      ) : (
        roots.map((r) => <TreeRow key={r.span.span_id} node={r} />)
      )}
    </div>
  );
}

function TreeRow({ node }: { node: TreeNode }) {
  const { selectedId, select } = useSelection();
  const [open, setOpen] = useState(true);
  const hasChildren = node.children.length > 0;
  const kind = kindOf(node.span);
  const swatch = kindSwatch(kind);
  const isSelected = node.span.span_id === selectedId;

  const totalTokens = extractTotalTokens(node.span);

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => select(node.span)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            select(node.span);
          }
        }}
        className={`group flex items-center gap-2 px-3 py-1.5 border-b border-[color:var(--border)]/50 cursor-pointer hover:bg-linen/[0.04] transition-colors ${
          isSelected ? "bg-drift-violet/10 border-l-2 border-l-drift-violet" : ""
        }`}
        style={{ paddingLeft: `${node.depth * 16 + 12}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(!open);
            }}
            className="w-4 h-4 flex items-center justify-center text-twilight hover:text-linen -ml-1 mr-1"
          >
            {open ? "▼" : "▶"}
          </button>
        ) : (
          <span className="w-4 h-4 inline-block" />
        )}
        <span
          className="text-[10px] uppercase tracking-wider w-16"
          style={{ color: swatch.fg }}
        >
          {kind}
        </span>
        <span className="flex-1 truncate text-linen">{node.span.name}</span>
        {totalTokens != null ? (
          <span className="text-[10px] text-twilight tabular-nums">
            {fmtTokens(totalTokens)}t
          </span>
        ) : null}
        <span className="text-[10px] text-twilight tabular-nums w-12 text-right">
          {fmtDuration(node.span.duration_ms)}
        </span>
        {node.span.status_code === "ERROR" ? (
          <span className="text-[10px] text-coral">!</span>
        ) : null}
      </div>
      {open && hasChildren ? (
        <div>
          {node.children.map((c) => (
            <TreeRow key={c.span.span_id} node={c} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
