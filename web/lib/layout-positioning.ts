/**
 * Place phase for sequence layout.
 *
 * Walks the already-sized LayoutNode tree and assigns x/y positions
 * relative to each parent. Dimensions must already be set by the sizing
 * module; this module only reads widths/heights.
 */

import {
  FRAME_PAD_X,
  FRAME_PAD_Y,
  FRAME_TITLE,
  PAR_GUTTER,
  SEQ_GUTTER,
} from "./layout-sizing";
import type { LayoutNode } from "./sequence-layout";

export function positionChildren(node: LayoutNode, all: LayoutNode[]): void {
  const children = all.filter((n) => n.parentId === node.id);
  if (children.length === 0) return;

  // Horizontal: parallel frames always, plus agent frames with all-compact kids.
  // We infer the latter from the node's own sizing — frames sized horizontally
  // have width == sum(children widths) + gutters + padding.
  const horizontal =
    node.frameKind === "parallel" ||
    (node.frameKind === "agent" &&
      approxEqual(
        node.width,
        children.reduce((sum, c) => sum + c.width, 0) +
          PAR_GUTTER * Math.max(0, children.length - 1) +
          FRAME_PAD_X * 2,
      ));

  if (horizontal) {
    let x = FRAME_PAD_X;
    const innerHeight = node.height - FRAME_TITLE - FRAME_PAD_Y * 2;
    const baseY = FRAME_TITLE + FRAME_PAD_Y;
    for (const c of children) {
      c.x = x;
      // Vertically center shorter children within the frame row.
      c.y = baseY + Math.max(0, (innerHeight - c.height) / 2);
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

export function approxEqual(a: number, b: number): boolean {
  return Math.abs(a - b) < 1;
}
