/**
 * Measure phase for sequence layout.
 *
 * Walks the TreeNode hierarchy, emits LayoutNodes into a flat list, and
 * assigns bottom-up widths/heights to frames. Positions (x/y) are not set
 * here — that is the positioning module's job.
 */

import type { Span } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { endMs, groupByParallel } from "@/lib/span-timing";
import type { TreeNode } from "@/lib/tree";
import type { FrameKind, LayoutNode } from "./sequence-layout";

// --- sizing constants ---
export const STEP_WIDTH = 240;
export const STEP_HEIGHT = 58;
export const EXPANDED_STEP_HEIGHT = 300;
export const FRAME_PAD_X = 16;
export const FRAME_PAD_Y = 14;
export const FRAME_TITLE = 32;
export const SEQ_GUTTER = 36; // vertical gap between sequence nodes — room for edge label
export const PAR_GUTTER = 56; // horizontal gap between parallel / horizontal-seq nodes

export type LayoutCtx = { expandedIds: Set<string>; expandAll: boolean };

// Agent frames lay out horizontally when their direct children are all
// leaf steps (linear sub-agent work reads left-to-right). If any child is
// itself a frame (nested sub-agent, parallel group), fall back to vertical
// so nested layouts don't cascade into impossibly wide rows.
export function shouldLayoutHorizontally(
  frame: LayoutNode,
  children: LayoutNode[],
  _ctx: LayoutCtx,
): boolean {
  if (frame.frameKind !== "agent") return false;
  return children.every((c) => c.kind === "step");
}

export function buildNode(
  treeNode: TreeNode,
  counter: { n: number },
  parentId: string | null,
  all: LayoutNode[],
  ctx: LayoutCtx,
): LayoutNode {
  const span = treeNode.span;
  const rawChildren = treeNode.children; // already sorted by start_at in buildTree
  const k = kindOf(span);

  if (rawChildren.length === 0) {
    counter.n += 1;
    const expanded = ctx.expandAll || ctx.expandedIds.has(span.span_id);
    const node: LayoutNode = {
      id: span.span_id,
      kind: "step",
      span,
      nodeKind: k,
      label: resolveLabel(span),
      execOrder: counter.n,
      parentId,
      width: STEP_WIDTH,
      height: expanded ? EXPANDED_STEP_HEIGHT : STEP_HEIGHT,
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
  const groups = groupByParallel(
    rawChildren,
    (tn) => new Date(tn.span.started_at).getTime(),
    (tn) => endMs(tn.span),
  );

  const frameChildIds: string[] = [];
  for (const group of groups) {
    if (group.length === 1) {
      const c = buildNode(group[0], counter, frameNode.id, all, ctx);
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
        const c = buildNode(s, counter, parNode.id, all, ctx);
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

  // Size the frame based on its layout direction.
  const frameChildren = frameChildIds.map((id) => all.find((n) => n.id === id)!);
  if (shouldLayoutHorizontally(frameNode, frameChildren, ctx)) {
    const innerW =
      frameChildren.reduce((sum, c) => sum + c.width, 0) +
      PAR_GUTTER * Math.max(0, frameChildren.length - 1);
    const innerH = Math.max(...frameChildren.map((c) => c.height));
    frameNode.width = innerW + FRAME_PAD_X * 2;
    frameNode.height = innerH + FRAME_TITLE + FRAME_PAD_Y * 2;
  } else {
    const innerW = Math.max(...frameChildren.map((c) => c.width));
    const innerH =
      frameChildren.reduce((sum, c) => sum + c.height, 0) +
      SEQ_GUTTER * Math.max(0, frameChildren.length - 1);
    frameNode.width = innerW + FRAME_PAD_X * 2;
    frameNode.height = innerH + FRAME_TITLE + FRAME_PAD_Y * 2;
  }

  return frameNode;
}

function resolveLabel(span: Span): string {
  const attrs = span.attributes;
  const nm =
    (attrs["langperf.node.name"] as string | undefined) ??
    (attrs["langperf.trajectory.name"] as string | undefined) ??
    span.name;
  return nm;
}
