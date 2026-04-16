"use client";

import { useMemo, useState } from "react";
import type { Span } from "@/lib/api";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { kindOf } from "@/lib/span-fields";
import { buildTree, type TreeNode } from "@/lib/tree";

const kindColors: Record<string, string> = {
  llm: "text-emerald-300",
  tool: "text-violet-300",
  agent: "text-sky-300",
  chain: "text-amber-300",
  retriever: "text-orange-300",
  embedding: "text-pink-300",
  reasoning: "text-teal-300",
  trajectory: "text-white",
};

function kindColor(kind: string): string {
  return kindColors[kind] ?? "text-[var(--muted)]";
}

export function TrajectoryTree({
  spans,
  selectedId,
  onSelect,
}: {
  spans: Span[];
  selectedId: string | null;
  onSelect: (span: Span) => void;
}) {
  const roots = useMemo(() => buildTree(spans), [spans]);
  return (
    <div className="text-sm font-mono">
      {roots.length === 0 ? (
        <div className="p-5 text-[var(--muted)]">No spans.</div>
      ) : (
        roots.map((r) => (
          <TreeRow
            key={r.span.span_id}
            node={r}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ))
      )}
    </div>
  );
}

function TreeRow({
  node,
  selectedId,
  onSelect,
}: {
  node: TreeNode;
  selectedId: string | null;
  onSelect: (span: Span) => void;
}) {
  const [open, setOpen] = useState(true);
  const hasChildren = node.children.length > 0;
  const kind = kindOf(node.span);
  const isSelected = node.span.span_id === selectedId;

  const totalTokens =
    (node.span.attributes["llm.token_count.total"] as number | undefined) ??
    (node.span.attributes["gen_ai.usage.total_tokens"] as number | undefined) ??
    null;

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => onSelect(node.span)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelect(node.span);
          }
        }}
        className={`group flex items-center gap-2 px-3 py-1.5 border-b border-[var(--border)]/50 cursor-pointer hover:bg-white/[0.04] ${
          isSelected ? "bg-[var(--accent)]/10 border-l-2 border-l-[var(--accent)]" : ""
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
            className="w-4 h-4 flex items-center justify-center text-[var(--muted)] hover:text-[var(--foreground)] -ml-1 mr-1"
          >
            {open ? "▼" : "▶"}
          </button>
        ) : (
          <span className="w-4 h-4 inline-block" />
        )}
        <span
          className={`text-[10px] uppercase tracking-wider w-16 ${kindColor(kind)}`}
        >
          {kind}
        </span>
        <span className="flex-1 truncate text-[var(--foreground)]">
          {node.span.name}
        </span>
        {totalTokens != null ? (
          <span className="text-[10px] text-[var(--muted)] tabular-nums">
            {fmtTokens(totalTokens)}t
          </span>
        ) : null}
        <span className="text-[10px] text-[var(--muted)] tabular-nums w-12 text-right">
          {fmtDuration(node.span.duration_ms)}
        </span>
        {node.span.status_code === "ERROR" ? (
          <span className="text-[10px] text-rose-400">!</span>
        ) : null}
      </div>
      {open && hasChildren ? (
        <div>
          {node.children.map((c) => (
            <TreeRow
              key={c.span.span_id}
              node={c}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
