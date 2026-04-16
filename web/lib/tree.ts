import type { Span } from "@/lib/api";

export type TreeNode = {
  span: Span;
  children: TreeNode[];
  depth: number;
};

export function buildTree(spans: Span[]): TreeNode[] {
  const byId = new Map<string, TreeNode>();
  for (const s of spans) byId.set(s.span_id, { span: s, children: [], depth: 0 });

  const roots: TreeNode[] = [];
  for (const s of spans) {
    const node = byId.get(s.span_id)!;
    const parent = s.parent_span_id ? byId.get(s.parent_span_id) : undefined;
    if (parent) {
      node.depth = parent.depth + 1;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }

  const byStart = (a: TreeNode, b: TreeNode) =>
    new Date(a.span.started_at).getTime() - new Date(b.span.started_at).getTime();

  const sortRec = (nodes: TreeNode[]) => {
    nodes.sort(byStart);
    for (const n of nodes) sortRec(n.children);
  };
  sortRec(roots);

  // Recompute depths after sorting (depth was provisional during tree build).
  const setDepth = (n: TreeNode, d: number) => {
    n.depth = d;
    for (const c of n.children) setDepth(c, d + 1);
  };
  for (const r of roots) setDepth(r, 0);

  return roots;
}

export function flattenTree(roots: TreeNode[]): TreeNode[] {
  const out: TreeNode[] = [];
  const walk = (n: TreeNode) => {
    out.push(n);
    for (const c of n.children) walk(c);
  };
  for (const r of roots) walk(r);
  return out;
}
