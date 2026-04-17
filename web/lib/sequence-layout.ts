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
 */

import type { Span } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { buildTree, type TreeNode } from "@/lib/tree";

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

// --- sizing constants ---
const STEP_WIDTH = 220;
const STEP_HEIGHT = 64;
const FRAME_PAD_X = 18;
const FRAME_PAD_Y = 16;
const FRAME_TITLE = 34;
const SEQ_GUTTER = 18;
const PAR_GUTTER = 24;
// Allow a small slop so trivial "serial" span timing quirks don't trigger a
// parallel frame (e.g. tool starts 3ms before the LLM's end timestamp).
const PARALLEL_TOLERANCE_MS = 60;

export function buildSequenceLayout(spans: Span[]): {
  all: LayoutNode[];
  rootIds: string[];
  maxExecOrder: number;
} {
  if (spans.length === 0) return { all: [], rootIds: [], maxExecOrder: 0 };

  // Delegate parent/child + sort-by-start to the canonical tree builder.
  // Sequence layout is the only other consumer of that relationship — we
  // own the overlap-detection and sizing on top, not the tree walk itself.
  const roots = buildTree(spans);

  const all: LayoutNode[] = [];
  const counter = { n: 0 };
  const rootIds: string[] = [];

  for (const root of roots) {
    const node = buildNode(root, counter, null, all);
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

function endMsOf(s: Span): number {
  if (s.ended_at) return new Date(s.ended_at).getTime();
  return new Date(s.started_at).getTime() + (s.duration_ms ?? 0);
}

function buildNode(
  treeNode: TreeNode,
  counter: { n: number },
  parentId: string | null,
  all: LayoutNode[],
): LayoutNode {
  const span = treeNode.span;
  const rawChildren = treeNode.children; // already sorted by start_at in buildTree
  const k = kindOf(span);

  if (rawChildren.length === 0) {
    counter.n += 1;
    const node: LayoutNode = {
      id: span.span_id,
      kind: "step",
      span,
      nodeKind: k,
      label: resolveLabel(span),
      execOrder: counter.n,
      parentId,
      width: STEP_WIDTH,
      height: STEP_HEIGHT,
      x: 0,
      y: 0,
    };
    all.push(node);
    return node;
  }

  // Has children → this is a frame. Decide the frame flavor from its kind.
  const frameKind: FrameKind =
    k === "trajectory" ? "trajectory" : k === "agent" ? "agent" : "container";

  const frameNode: LayoutNode = {
    id: span.span_id,
    kind: "frame",
    frameKind,
    span,
    nodeKind: k,
    label: resolveLabel(span),
    parentId,
    width: 0,
    height: 0,
    x: 0,
    y: 0,
  };
  all.push(frameNode);

  // Group consecutive children that overlap in time into parallel frames.
  const groups = groupByParallel(rawChildren);

  const frameChildIds: string[] = [];
  for (const group of groups) {
    if (group.length === 1) {
      const c = buildNode(group[0], counter, frameNode.id, all);
      frameChildIds.push(c.id);
    } else {
      // Synthetic parallel frame
      const parId = `par:${span.span_id}:${group
        .map((s) => s.span.span_id.slice(0, 6))
        .join(",")}`;
      const parNode: LayoutNode = {
        id: parId,
        kind: "frame",
        frameKind: "parallel",
        span: null,
        nodeKind: "parallel",
        label: `${group.length} parallel`,
        parentId: frameNode.id,
        width: 0,
        height: 0,
        x: 0,
        y: 0,
      };
      all.push(parNode);
      const parChildIds: string[] = [];
      for (const s of group) {
        const c = buildNode(s, counter, parNode.id, all);
        parChildIds.push(c.id);
      }
      // Size parallel frame (horizontal layout of branches)
      const branches = parChildIds.map((id) => all.find((n) => n.id === id)!);
      const w =
        branches.reduce((sum, b) => sum + b.width, 0) +
        PAR_GUTTER * Math.max(0, branches.length - 1) +
        FRAME_PAD_X * 2;
      const h =
        Math.max(...branches.map((b) => b.height)) + FRAME_TITLE + FRAME_PAD_Y * 2;
      parNode.width = w;
      parNode.height = h;
      frameChildIds.push(parNode.id);
    }
  }

  // Size frame (vertical stack of its children)
  const frameChildren = frameChildIds.map((id) => all.find((n) => n.id === id)!);
  const innerW = Math.max(...frameChildren.map((c) => c.width));
  const innerH =
    frameChildren.reduce((sum, c) => sum + c.height, 0) +
    SEQ_GUTTER * Math.max(0, frameChildren.length - 1);
  frameNode.width = innerW + FRAME_PAD_X * 2;
  frameNode.height = innerH + FRAME_TITLE + FRAME_PAD_Y * 2;

  return frameNode;
}

function positionChildren(node: LayoutNode, all: LayoutNode[]): void {
  const children = all.filter((n) => n.parentId === node.id);
  if (children.length === 0) return;

  if (node.frameKind === "parallel") {
    // Horizontal layout: branches side-by-side, top-aligned.
    let x = FRAME_PAD_X;
    const y = FRAME_TITLE + FRAME_PAD_Y;
    for (const c of children) {
      c.x = x;
      c.y = y;
      positionChildren(c, all);
      x += c.width + PAR_GUTTER;
    }
    return;
  }

  // Vertical sequence layout; center each child horizontally within the frame.
  let y = FRAME_TITLE + FRAME_PAD_Y;
  const innerWidth = node.width - FRAME_PAD_X * 2;
  for (const c of children) {
    c.x = FRAME_PAD_X + Math.max(0, (innerWidth - c.width) / 2);
    c.y = y;
    positionChildren(c, all);
    y += c.height + SEQ_GUTTER;
  }
}

function groupByParallel(siblings: TreeNode[]): TreeNode[][] {
  if (siblings.length === 0) return [];
  const groups: TreeNode[][] = [];
  let current: TreeNode[] = [siblings[0]];
  let currentEnd = endMsOf(siblings[0].span);
  for (let i = 1; i < siblings.length; i++) {
    const tn = siblings[i];
    const startMs = new Date(tn.span.started_at).getTime();
    if (startMs < currentEnd - PARALLEL_TOLERANCE_MS) {
      // overlaps with the running group → parallel
      current.push(tn);
      currentEnd = Math.max(currentEnd, endMsOf(tn.span));
    } else {
      groups.push(current);
      current = [tn];
      currentEnd = endMsOf(tn.span);
    }
  }
  groups.push(current);
  return groups;
}

function resolveLabel(span: Span): string {
  const attrs = span.attributes;
  const nm =
    (attrs["langperf.node.name"] as string | undefined) ??
    (attrs["langperf.trajectory.name"] as string | undefined) ??
    span.name;
  return nm;
}
