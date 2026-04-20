/**
 * Build a hierarchical layout tree from a flat list of spans.
 *
 * Shape:
 *   - Containers (trajectory / agent / parallel) wrap their children.
 *   - Leaf steps are the actual operations (llm / tool / reasoning / etc).
 *   - Siblings whose time ranges overlap become a `parallel` container
 *     (rendered as a dashed frame in the UI).
 *
 * Positions are RELATIVE TO PARENT — React Flow's compound-node convention.
 * Widths/heights are measured bottom-up; positions assigned top-down.
 *
 * This module is the orchestrator: it wires together the measure phase
 * (layout-sizing) and the place phase (layout-positioning). The canonical
 * LayoutNode type lives here so both phases can import it without cycles.
 */

import type { Span } from "@/lib/api";
import { buildTree } from "@/lib/tree";
import { buildNode, SEQ_GUTTER } from "./layout-sizing";
import { positionChildren } from "./layout-positioning";

export type FrameKind = "trajectory" | "agent" | "parallel" | "container";

export type LayoutNode = {
  id: string;
  kind: "step" | "frame";
  frameKind?: FrameKind;
  span: Span | null; // null for synthetic parallel frames
  nodeKind: string; // "llm" | "tool" | "agent" | "parallel" | "trajectory" | etc
  label: string;
  execOrder?: number; // 1-based, leaves only
  parentId: string | null;
  width: number;
  height: number;
  x: number; // relative to parent
  y: number;
};

export type LayoutOptions = {
  expandedIds?: Set<string>;
  expandAll?: boolean;
};

export function buildSequenceLayout(
  spans: Span[],
  opts: LayoutOptions = {},
): {
  all: LayoutNode[];
  rootIds: string[];
  maxExecOrder: number;
} {
  if (spans.length === 0) return { all: [], rootIds: [], maxExecOrder: 0 };

  const expandedIds = opts.expandedIds ?? new Set<string>();
  const expandAll = opts.expandAll ?? false;

  // Delegate parent/child + sort-by-start to the canonical tree builder.
  const roots = buildTree(spans);

  const all: LayoutNode[] = [];
  const counter = { n: 0 };
  const rootIds: string[] = [];
  const ctx = { expandedIds, expandAll };

  for (const root of roots) {
    const node = buildNode(root, counter, null, all, ctx);
    rootIds.push(node.id);
  }

  // Layout: position relative to each parent.
  for (const n of all.filter((x) => !x.parentId)) {
    positionChildren(n, all);
  }

  // Stack multiple root frames vertically (spaced) if there are several.
  let yCursor = 0;
  for (const id of rootIds) {
    const n = all.find((x) => x.id === id);
    if (!n) continue;
    n.x = 0;
    n.y = yCursor;
    yCursor += n.height + SEQ_GUTTER;
  }

  return { all, rootIds, maxExecOrder: counter.n };
}
