# Trajectory Graph Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the trajectory graph into a flat, data-rich, full-screenable surface with inline input/output on nodes, labelled edges, a resizable Detail/Notes/Thread sidebar, and per-node comment threads.

**Architecture:** Additive frontend changes. No backend, no schema, no API. New files under `web/components/graph/` and `web/components/sidebar/`. Trajectory-view and node-detail-panel refactor to mount new providers and tabbed sidebar. React Flow (`@xyflow/react`) stays. Comments reuse v2b components/endpoints verbatim.

**Tech Stack:** Next.js 14 App Router, React 18, TypeScript, Tailwind v3, `@xyflow/react`, Playwright for E2E.

**Spec:** `docs/superpowers/specs/2026-04-19-graph-redesign.md`

---

## File structure

**New (frontend only):**

| Path | Responsibility |
|---|---|
| `web/components/graph/fullscreen-context.tsx` | `FullscreenProvider` / `useFullscreen()` — holds `fsOpen`, `toggleFs`, `expandAll`, `toggleExpandAll`, `expandedIds: Set<string>`, `toggleExpand(id)` |
| `web/lib/expand-state.ts` | `useExpandState(spanId)` hook — returns `[expanded, toggle]`; composes global + per-id overrides |
| `web/components/graph/graph-toolbar.tsx` | Top-right pill-button toolbar: expand-all / compact-all / full-screen toggles |
| `web/components/graph/flat-node-compact.tsx` | Replacement for `StepNodeComp` compact state |
| `web/components/graph/flat-node-expanded.tsx` | Expanded card shell; dispatches on `kindOf(span)` to one of three bodies |
| `web/components/graph/expanded-tool-body.tsx` | `ARGS IN` / `RESULT OUT` blocks |
| `web/components/graph/expanded-llm-body.tsx` | Role-chipped input + output + tool-call summaries + stats footer |
| `web/components/graph/expanded-frame-body.tsx` | Thin banner for agent/parallel frames |
| `web/lib/graph-edges.ts` | Pure `buildEdges(spans: Span[]): Edge[]` with semantic labels |
| `web/components/graph/labelled-edge.tsx` | React Flow custom edge: line + label chip + click-to-reveal JSON peek |
| `web/components/graph/floating-inspector.tsx` | Full-screen bottom-right overlay card for selected span |
| `web/components/sidebar/resizable-sidebar.tsx` | Resizer handle + collapse chevron + localStorage persistence |
| `web/components/sidebar/sidebar-tabs.tsx` | Controlled tab strip (Detail · Notes · Thread) |
| `web/components/collab/node-thread.tsx` | Wrapper around v2b `CommentThread` + `CommentComposer` scoped to a span |
| `web/lib/comment-counts.ts` | `useCommentCounts(trajectoryId): Map<spanId, number>` (fetches on mount) |

**Refactor (existing):**

| Path | Change |
|---|---|
| `web/components/trajectory-graph.tsx` | Use new node types, plug labelled edges, wire toolbar + fullscreen context |
| `web/components/trajectory-view.tsx` | Mount `FullscreenProvider`, switch between split and full-screen layouts, URL param sync |
| `web/components/node-detail-panel.tsx` | Wrap in `ResizableSidebar`; use `SidebarTabs` with Detail/Notes/Thread |

---

## Task 1: FullscreenContext + expand-state hook + toolbar scaffolding

**Files:**
- Create: `web/components/graph/fullscreen-context.tsx`
- Create: `web/lib/expand-state.ts`
- Create: `web/components/graph/graph-toolbar.tsx`
- Test: `web/tests/graph-toolbar.spec.ts`

**Rationale:** Everything else reads/writes this state. Build it first so subsequent tasks can wire into it.

- [ ] **Step 1: Write Playwright test for the toolbar**

Create `web/tests/graph-toolbar.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId } from "./_helpers";

test("graph toolbar shows expand/compact/fullscreen controls", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);
  await expect(page.getByRole("button", { name: /expand all/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /compact all/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /full.?screen/i })).toBeVisible();
});
```

- [ ] **Step 2: Run, expect failure** (`expand all` button doesn't exist yet)

```bash
cd web && npx playwright test graph-toolbar.spec.ts --project=chromium
```

Expected: FAIL with "timed out waiting for locator… expand all".

- [ ] **Step 3: Implement FullscreenContext**

`web/components/graph/fullscreen-context.tsx`:

```tsx
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type FullscreenValue = {
  fsOpen: boolean;
  toggleFs: () => void;
  setFs: (open: boolean) => void;
  expandAll: boolean;
  toggleExpandAll: () => void;
  expandedIds: Set<string>;
  toggleExpand: (spanId: string) => void;
  collapseAll: () => void;
};

const Ctx = createContext<FullscreenValue | null>(null);

export function FullscreenProvider({
  initialFs = false,
  children,
}: {
  initialFs?: boolean;
  children: ReactNode;
}) {
  const [fsOpen, setFs] = useState(initialFs);
  const [expandAll, setExpandAll] = useState(false);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleFs = useCallback(() => setFs((v) => !v), []);
  const toggleExpandAll = useCallback(() => {
    setExpandAll((v) => !v);
    setExpandedIds(new Set()); // global toggle resets per-id overrides
  }, []);
  const toggleExpand = useCallback((spanId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(spanId)) next.delete(spanId);
      else next.add(spanId);
      return next;
    });
  }, []);
  const collapseAll = useCallback(() => {
    setExpandAll(false);
    setExpandedIds(new Set());
  }, []);

  const value = useMemo<FullscreenValue>(
    () => ({
      fsOpen,
      toggleFs,
      setFs,
      expandAll,
      toggleExpandAll,
      expandedIds,
      toggleExpand,
      collapseAll,
    }),
    [fsOpen, toggleFs, expandAll, toggleExpandAll, expandedIds, toggleExpand, collapseAll],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFullscreen(): FullscreenValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useFullscreen must be used inside <FullscreenProvider>");
  return v;
}
```

- [ ] **Step 4: Implement expand-state hook**

`web/lib/expand-state.ts`:

```ts
"use client";

import { useFullscreen } from "@/components/graph/fullscreen-context";

/**
 * Returns [expanded, toggle] for a given span.
 *
 * Precedence:
 *  - If global `expandAll` is on → expanded is true.
 *  - Else per-span override in `expandedIds`.
 *
 * `toggle` always toggles the per-span override. When global expandAll is
 * on and the user clicks a node to collapse it, that's an intentional
 * per-span override of the global state; we represent this by flipping the
 * global to off and seeding the override set with every other span's id —
 * which is out of scope here. Simpler v1: while expandAll is on, per-span
 * toggles are no-ops. The compact-all toolbar button is the way out.
 */
export function useExpandState(spanId: string): [boolean, () => void] {
  const { expandAll, expandedIds, toggleExpand } = useFullscreen();
  const expanded = expandAll || expandedIds.has(spanId);
  return [expanded, () => toggleExpand(spanId)];
}
```

- [ ] **Step 5: Implement graph toolbar**

`web/components/graph/graph-toolbar.tsx`:

```tsx
"use client";

import { useFullscreen } from "@/components/graph/fullscreen-context";

export function GraphToolbar() {
  const { fsOpen, toggleFs, expandAll, toggleExpandAll, collapseAll } =
    useFullscreen();

  return (
    <div className="absolute top-2 right-2 z-10 flex items-center gap-1 bg-[color:var(--surface)] border border-[color:var(--border)] rounded-md p-1">
      <ToolbarButton
        label="expand all"
        active={expandAll}
        onClick={toggleExpandAll}
        title="Expand every node (E)"
      />
      <ToolbarButton
        label="compact all"
        onClick={collapseAll}
        title="Collapse every node (C)"
      />
      <div className="w-px h-4 bg-[color:var(--border)] mx-1" />
      <ToolbarButton
        label={fsOpen ? "exit full-screen" : "full-screen"}
        active={fsOpen}
        onClick={toggleFs}
        title="Toggle full-screen (F)"
      />
    </div>
  );
}

function ToolbarButton({
  label,
  onClick,
  active = false,
  title,
}: {
  label: string;
  onClick: () => void;
  active?: boolean;
  title?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={label}
      className={`px-2 py-1 text-[10px] uppercase tracking-wider font-mono rounded transition-colors ${
        active
          ? "bg-aether-teal/15 text-aether-teal"
          : "text-warm-fog/70 hover:text-warm-fog hover:bg-warm-fog/5"
      }`}
    >
      {label}
    </button>
  );
}
```

- [ ] **Step 6: Wire provider + toolbar into trajectory-view and trajectory-graph (minimum surface)**

Edit `web/components/trajectory-view.tsx` at the top of imports:

```tsx
import { FullscreenProvider } from "@/components/graph/fullscreen-context";
```

Wrap the existing `SelectionProvider` children with `FullscreenProvider`:

```tsx
<SelectionProvider spans={trajectory.spans} initialId={firstSpanId}>
  <FullscreenProvider>
    {/* existing JSX */}
  </FullscreenProvider>
</SelectionProvider>
```

Edit `web/components/trajectory-graph.tsx`, add at the imports:

```tsx
import { GraphToolbar } from "@/components/graph/graph-toolbar";
```

Inside `TrajectoryGraph`, wrap `<ReactFlow>` in a `relative` container and render the toolbar above it:

```tsx
return (
  <div className="w-full h-full bg-midnight relative">
    <GraphToolbar />
    <ReactFlow
      {/* unchanged */}
    >
      {/* unchanged */}
    </ReactFlow>
  </div>
);
```

- [ ] **Step 7: Run Playwright, expect pass**

```bash
cd web && npx playwright test graph-toolbar.spec.ts --project=chromium
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/components/graph/fullscreen-context.tsx \
        web/components/graph/graph-toolbar.tsx \
        web/lib/expand-state.ts \
        web/components/trajectory-view.tsx \
        web/components/trajectory-graph.tsx \
        web/tests/graph-toolbar.spec.ts
git commit -m "feat(graph): fullscreen context + expand-state hook + toolbar scaffolding"
```

---

## Task 2: Flat compact node + kind accent (no gradients)

**Files:**
- Create: `web/components/graph/flat-node-compact.tsx`
- Modify: `web/components/trajectory-graph.tsx:28-81` (replace `StepNodeComp` with `FlatNodeCompact`)
- Modify: `web/components/trajectory-graph.tsx:83-153` (flatten `FrameNodeComp` — drop gradient on title bar)
- Test: `web/tests/graph-flat-node.spec.ts`

- [ ] **Step 1: Write the failing test**

`web/tests/graph-flat-node.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId } from "./_helpers";

test("compact node has no gradient + shows kind stripe", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  const node = page.locator('[data-node-kind="llm"]').first();
  await expect(node).toBeVisible();
  const bg = await node.evaluate((el) => getComputedStyle(el).backgroundImage);
  expect(bg).toBe("none"); // asserts no linear-gradient on the card

  // Kind stripe: check for borderLeft
  const borderLeft = await node.evaluate((el) => getComputedStyle(el).borderLeftWidth);
  expect(parseFloat(borderLeft)).toBeGreaterThanOrEqual(3);
});
```

- [ ] **Step 2: Run, expect failure** — `[data-node-kind="llm"]` attribute doesn't exist yet.

```bash
cd web && npx playwright test graph-flat-node.spec.ts --project=chromium
```

- [ ] **Step 3: Implement FlatNodeCompact**

`web/components/graph/flat-node-compact.tsx`:

```tsx
"use client";

import type { NodeProps, Node } from "@xyflow/react";
import type { LayoutNode } from "@/lib/sequence-layout";
import { KIND_GLYPH, KIND_LABEL, kindSwatch } from "@/lib/colors";
import { fmtDuration, fmtTokens } from "@/lib/format";
import { extractTotalTokens } from "@/lib/span-fields";

export type FlatStepData = {
  layout: LayoutNode;
  selected: boolean;
  commentCount: number;
  onToggle: () => void;
};
type FlatStepNode = Node<FlatStepData, "step">;

export function FlatNodeCompact({ data }: NodeProps<FlatStepNode>) {
  const { layout, selected, commentCount, onToggle } = data;
  const { span, nodeKind, execOrder } = layout;
  const swatch = kindSwatch(nodeKind);
  const tokens = extractTotalTokens(span);
  const isError = span?.status_code === "ERROR";

  return (
    <div
      data-node-kind={nodeKind}
      data-selected={selected ? "true" : "false"}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      className="relative cursor-pointer transition-colors"
      style={{
        width: layout.width,
        height: layout.height,
        background: "var(--surface)",
        border: `1px solid ${selected ? "var(--accent)" : "var(--border)"}`,
        borderLeft: `3px solid ${isError ? "var(--warn)" : swatch.fg}`,
        borderRadius: 6,
        boxShadow: selected
          ? "0 0 0 2px rgba(107,186,177,0.25)"
          : "none",
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
  );
}
```

- [ ] **Step 4: Flatten FrameNodeComp in trajectory-graph.tsx**

In `web/components/trajectory-graph.tsx`, replace lines 83–153 (`FrameNodeComp`) with:

```tsx
function FrameNodeComp({ data }: NodeProps<FrameNode>) {
  const { layout, selected } = data;
  const { frameKind, label, span, nodeKind } = layout;
  const tokens = extractTotalTokens(span);
  const duration = span?.duration_ms ?? null;

  if (frameKind === "parallel") {
    return (
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
    );
  }

  const swatch = kindSwatch(nodeKind);

  return (
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
  );
}
```

Key diff: removed `titleBg = linear-gradient(...)`; removed the rgba `background` with implied glow; reduced borders to 1px solid + 3px kind stripe; dropped the 12px border radius to 6px for consistency with steps.

- [ ] **Step 5: Wire FlatNodeCompact into the node types map**

Replace the `nodeTypes` constant and the inline `StepNodeComp` function in `web/components/trajectory-graph.tsx` (lines 28–81, 155–158). New content for those lines:

```tsx
import { FlatNodeCompact, type FlatStepData } from "@/components/graph/flat-node-compact";

// ...StepNodeComp + FrameNodeComp above...

const nodeTypes = {
  step: FlatNodeCompact,
  frame: FrameNodeComp,
};
```

In `TrajectoryGraph`'s `rfNodes` construction, build the step `data` using `FlatStepData`:

```tsx
const onToggle = useCallback((spanId: string) => () => toggleExpand(spanId), [toggleExpand]);
// ...
data: ln.kind === "step"
  ? ({
      layout: ln,
      selected: ln.span?.span_id === selectedId,
      commentCount: 0, // populated in Task 7
      onToggle: () => ln.span && toggleExpand(ln.span.span_id),
    } satisfies FlatStepData)
  : ({
      layout: ln,
      selected: ln.span?.span_id === selectedId,
    } satisfies FrameData),
```

Add at the top of `TrajectoryGraph`:

```tsx
import { useFullscreen } from "@/components/graph/fullscreen-context";
// inside the component:
const { toggleExpand } = useFullscreen();
```

Remove the now-unused imports (`DRIFT` stays only if FrameNodeComp still references it — it doesn't after the flatten; delete that import too).

- [ ] **Step 6: Run Playwright, expect pass**

```bash
cd web && npx playwright test graph-flat-node.spec.ts --project=chromium
```

Expected: PASS.

- [ ] **Step 7: Eyeball the change**

```bash
# ensure docker compose is up
docker compose ps | grep langperf-web
```

Open any trajectory in a browser; confirm nodes have a solid dark fill, a single kind-colored left stripe, and no gradient on frame title bars.

- [ ] **Step 8: Commit**

```bash
git add web/components/graph/flat-node-compact.tsx \
        web/components/trajectory-graph.tsx \
        web/tests/graph-flat-node.spec.ts
git commit -m "feat(graph): flat compact nodes — kill gradients, add kind stripe"
```

---

## Task 3: Labelled edges + graph-edges builder

**Files:**
- Create: `web/lib/graph-edges.ts`
- Create: `web/components/graph/labelled-edge.tsx`
- Modify: `web/components/trajectory-graph.tsx` — pass `edges` + `edgeTypes` to `ReactFlow`
- Test: `web/tests/graph-edges.spec.ts`

- [ ] **Step 1: Write the failing test**

`web/tests/graph-edges.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId } from "./_helpers";

test("graph renders labelled edges between sibling spans", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  // Edges render inside the React Flow SVG. Label chips are foreignObject
  // divs with data-edge-label.
  const labels = page.locator('[data-edge-label]');
  await expect(labels.first()).toBeVisible();
  const count = await labels.count();
  expect(count).toBeGreaterThan(0);
});

test("clicking an edge label toggles JSON peek", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  const label = page.locator('[data-edge-label]').first();
  await label.click();
  await expect(label).toHaveAttribute("data-expanded", "true");
  await label.click();
  await expect(label).toHaveAttribute("data-expanded", "false");
});
```

- [ ] **Step 2: Run, expect failure** — no edges rendered currently.

```bash
cd web && npx playwright test graph-edges.spec.ts --project=chromium
```

- [ ] **Step 3: Implement graph-edges builder**

`web/lib/graph-edges.ts`:

```ts
import type { Edge } from "@xyflow/react";
import type { Span } from "./api";
import { kindOf } from "./span-fields";

export type LabelledEdgeData = {
  label: string; // short tag like "tool:bash", "return", "message"
  payload?: string; // optional pretty-printed JSON preview (<= 50 chars)
};

/**
 * Builds edges connecting sibling spans in execution order. Siblings are
 * spans that share a `parent_span_id`. Labels are derived from the source
 * span's kind + attributes.
 *
 * This is not a dataflow graph — it's a *sequence* graph. Each parent-group
 * gets N-1 edges between consecutively-started children.
 */
export function buildEdges(spans: Span[]): Edge<LabelledEdgeData>[] {
  const byParent = new Map<string | null, Span[]>();
  for (const s of spans) {
    const key = s.parent_span_id;
    if (!byParent.has(key)) byParent.set(key, []);
    byParent.get(key)!.push(s);
  }

  const edges: Edge<LabelledEdgeData>[] = [];
  for (const siblings of byParent.values()) {
    siblings.sort(
      (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
    );
    for (let i = 1; i < siblings.length; i++) {
      const from = siblings[i - 1];
      const to = siblings[i];
      const label = edgeLabel(from, to);
      const payload = edgePayload(from, to);
      edges.push({
        id: `e-${from.span_id}-${to.span_id}`,
        source: from.span_id,
        target: to.span_id,
        type: "labelled",
        data: { label, payload },
      });
    }
  }
  return edges;
}

function edgeLabel(from: Span, to: Span): string {
  const fromKind = kindOf(from);
  const toKind = kindOf(to);
  if (fromKind === "llm" && toKind === "tool") {
    const name = toolName(to) ?? "tool";
    return `tool:${name}`;
  }
  if (fromKind === "tool" && toKind === "llm") return "return";
  if (fromKind === "llm" && toKind === "llm") return "message";
  return "→";
}

function toolName(span: Span): string | null {
  const attrs = span.attributes as Record<string, unknown> | null;
  if (!attrs) return null;
  const candidates = ["tool.name", "gen_ai.tool.name", "name"];
  for (const k of candidates) {
    const v = attrs[k];
    if (typeof v === "string" && v) return v;
  }
  return null;
}

function edgePayload(from: Span, to: Span): string | undefined {
  const fromKind = kindOf(from);
  const toKind = kindOf(to);
  // For tool calls we surface the first 50 chars of the tool input.
  if (fromKind === "llm" && toKind === "tool") {
    const input = firstToolInput(to);
    return input ? truncate(pretty(input), 50) : undefined;
  }
  // For tool→llm returns, surface the tool output.
  if (fromKind === "tool" && toKind === "llm") {
    const out = toolOutput(from);
    return out != null ? truncate(pretty(out), 50) : undefined;
  }
  return undefined;
}

function firstToolInput(span: Span): unknown {
  const a = span.attributes as Record<string, unknown> | null;
  if (!a) return null;
  for (const k of ["tool.arguments", "gen_ai.tool.arguments", "input", "parameters"]) {
    if (a[k] != null) return a[k];
  }
  return null;
}

function toolOutput(span: Span): unknown {
  const a = span.attributes as Record<string, unknown> | null;
  if (!a) return null;
  for (const k of ["tool.output", "gen_ai.tool.output", "output", "result"]) {
    if (a[k] != null) return a[k];
  }
  return null;
}

function pretty(v: unknown): string {
  if (typeof v === "string") return v;
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
```

- [ ] **Step 4: Implement labelled-edge component**

`web/components/graph/labelled-edge.tsx`:

```tsx
"use client";

import { useState } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import type { LabelledEdgeData } from "@/lib/graph-edges";

export function LabelledEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps & { data?: LabelledEdgeData }) {
  const [expanded, setExpanded] = useState(false);
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 8,
  });

  return (
    <>
      <BaseEdge id={id} path={edgePath} style={{ stroke: "var(--border-strong)", strokeWidth: 1 }} />
      <EdgeLabelRenderer>
        <div
          data-edge-label=""
          data-expanded={expanded ? "true" : "false"}
          onClick={(e) => {
            e.stopPropagation();
            if (data?.payload) setExpanded((v) => !v);
          }}
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: "all",
            fontFamily:
              'ui-monospace, "SF Mono", Menlo, monospace',
            fontSize: 9,
            textTransform: "uppercase",
            letterSpacing: "0.06em",
            color: "var(--muted)",
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 3,
            padding: expanded ? "4px 8px" : "1px 6px",
            cursor: data?.payload ? "pointer" : "default",
            maxWidth: expanded ? 240 : undefined,
            whiteSpace: expanded ? "normal" : "nowrap",
            zIndex: 1,
          }}
        >
          <div>{data?.label ?? "→"}</div>
          {expanded && data?.payload ? (
            <div
              style={{
                marginTop: 4,
                color: "var(--foreground)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                fontSize: 10,
              }}
            >
              {data.payload}
            </div>
          ) : null}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
```

- [ ] **Step 5: Wire edges into ReactFlow**

Edit `web/components/trajectory-graph.tsx`:

Add imports:

```tsx
import { buildEdges } from "@/lib/graph-edges";
import { LabelledEdge } from "@/components/graph/labelled-edge";
```

Add:

```tsx
const edgeTypes = { labelled: LabelledEdge };
```

In `TrajectoryGraph`, build edges:

```tsx
const rfEdges = useMemo(() => buildEdges(spans), [spans]);
```

Replace `edges={[]}` with `edges={rfEdges}` and add `edgeTypes={edgeTypes}`:

```tsx
<ReactFlow
  nodes={rfNodes}
  edges={rfEdges}
  nodeTypes={nodeTypes}
  edgeTypes={edgeTypes}
  /* ...rest unchanged */
>
```

- [ ] **Step 6: Run Playwright, expect pass**

```bash
cd web && npx playwright test graph-edges.spec.ts --project=chromium
```

Expected: both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web/lib/graph-edges.ts \
        web/components/graph/labelled-edge.tsx \
        web/components/trajectory-graph.tsx \
        web/tests/graph-edges.spec.ts
git commit -m "feat(graph): labelled edges with click-to-reveal JSON peek"
```

---

## Task 4: Expanded node bodies (tool, LLM, frame)

**Files:**
- Create: `web/components/graph/flat-node-expanded.tsx`
- Create: `web/components/graph/expanded-tool-body.tsx`
- Create: `web/components/graph/expanded-llm-body.tsx`
- Create: `web/components/graph/expanded-frame-body.tsx`
- Modify: `web/components/trajectory-graph.tsx` — swap node between compact / expanded on `useExpandState`
- Modify: `web/lib/sequence-layout.ts` — increase node height when expanded (new helper)
- Test: `web/tests/graph-expanded.spec.ts`

**Note:** Expanding a node grows its height. React Flow uses the `style.width/height` set in `nodes[]` — so the graph component must recompute node sizes when expansion changes. We accept a simple approach: expanded step nodes get a fixed `320px` height; we don't re-run the sequence layout (overlaps possible for very dense runs; acceptable for v1).

- [ ] **Step 1: Write the failing test**

`web/tests/graph-expanded.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId } from "./_helpers";

test("clicking a node reveals inline args/out", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  const node = page.locator('[data-node-kind="tool"]').first();
  await expect(node).toBeVisible();

  // Body not visible by default
  const body = node.locator('[data-expanded-body]');
  await expect(body).toHaveCount(0);

  await node.click();
  await expect(node.locator('[data-expanded-body]')).toBeVisible();
  await expect(node.getByText(/ARGS IN/i)).toBeVisible();
  await expect(node.getByText(/RESULT OUT/i)).toBeVisible();
});

test("expand all reveals every node's body", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  await page.getByRole("button", { name: /expand all/i }).click();
  const bodies = page.locator('[data-expanded-body]');
  const count = await bodies.count();
  expect(count).toBeGreaterThan(0);
});
```

- [ ] **Step 2: Run, expect failure**

```bash
cd web && npx playwright test graph-expanded.spec.ts --project=chromium
```

- [ ] **Step 3: Implement expanded tool body**

`web/components/graph/expanded-tool-body.tsx`:

```tsx
"use client";

import type { Span } from "@/lib/api";
import { extractToolFields } from "@/lib/span-fields";

const MAX = 200;

export function ExpandedToolBody({ span }: { span: Span }) {
  const f = extractToolFields(span.attributes);
  const input = f.input ?? f.parameters ?? span.attributes;
  const output = f.output;

  return (
    <div data-expanded-body className="text-[11px]">
      <Block label="ARGS IN" value={input} />
      {output != null ? <Block label="RESULT OUT" value={output} /> : null}
    </div>
  );
}

function Block({ label, value }: { label: string; value: unknown }) {
  const pretty =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const truncated = pretty.length > MAX ? pretty.slice(0, MAX) + "…" : pretty;
  return (
    <div className="mb-2 last:mb-0">
      <div className="text-[9px] uppercase tracking-wider text-warm-fog/60 mb-1">
        {label}
      </div>
      <pre
        className="font-mono text-[10px] whitespace-pre-wrap break-words p-2 rounded"
        style={{
          background: "var(--background)",
          border: "1px solid var(--border)",
          color: "var(--foreground)",
          lineHeight: 1.5,
        }}
      >
        {truncated}
      </pre>
    </div>
  );
}
```

- [ ] **Step 4: Implement expanded LLM body**

`web/components/graph/expanded-llm-body.tsx`:

```tsx
"use client";

import type { Span } from "@/lib/api";
import { extractLlmFields, type LlmMessage } from "@/lib/span-fields";
import { roleSwatch } from "@/lib/colors";

const MSG_MAX = 120;

export function ExpandedLlmBody({ span }: { span: Span }) {
  const f = extractLlmFields(span.attributes);

  return (
    <div data-expanded-body className="text-[11px]">
      {f.input_messages.length > 0 ? (
        <div className="mb-2">
          <div className="text-[9px] uppercase tracking-wider text-warm-fog/60 mb-1">
            INPUT
          </div>
          <div className="space-y-1">
            {f.input_messages.map((m, i) => (
              <MsgLine key={i} message={m} />
            ))}
          </div>
        </div>
      ) : null}

      {f.output_messages.length > 0 ? (
        <div className="mb-2">
          <div className="text-[9px] uppercase tracking-wider text-warm-fog/60 mb-1">
            OUTPUT
          </div>
          <div className="space-y-1">
            {f.output_messages.map((m, i) => (
              <MsgLine key={i} message={m} />
            ))}
          </div>
        </div>
      ) : null}

      <div
        className="flex gap-3 pt-2 mt-2 font-mono text-[10px] text-warm-fog/60"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        {f.tokens.prompt != null ? (
          <span>
            prompt <span className="text-warm-fog">{f.tokens.prompt}t</span>
          </span>
        ) : null}
        {f.tokens.completion != null ? (
          <span>
            compl <span className="text-warm-fog">{f.tokens.completion}t</span>
          </span>
        ) : null}
        {f.model ? (
          <span className="truncate">
            model <span className="text-warm-fog">{f.model}</span>
          </span>
        ) : null}
      </div>
    </div>
  );
}

function MsgLine({ message }: { message: LlmMessage }) {
  const sw = roleSwatch(message.role);
  const content = message.content ?? "";
  const truncated =
    content.length > MSG_MAX ? content.slice(0, MSG_MAX) + "…" : content;
  return (
    <div className="flex items-start gap-1.5 leading-relaxed">
      <span
        className="text-[9px] uppercase tracking-wider font-mono flex-shrink-0 px-1 rounded"
        style={{ color: sw.fg, border: `1px solid ${sw.border}` }}
      >
        {roleLabel(message.role)}
      </span>
      <span className="flex-1 text-warm-fog truncate">{truncated}</span>
      {message.tool_calls?.length ? (
        <span className="text-peach-neon flex-shrink-0 font-mono">
          → {message.tool_calls.map((tc) => tc.name).join(", ")}
        </span>
      ) : null}
    </div>
  );
}

function roleLabel(role: string): string {
  switch (role.toLowerCase()) {
    case "system":
      return "sys";
    case "user":
      return "usr";
    case "assistant":
      return "asst";
    case "tool":
      return "tool";
    default:
      return role.slice(0, 4);
  }
}
```

- [ ] **Step 5: Implement expanded frame body**

`web/components/graph/expanded-frame-body.tsx`:

```tsx
"use client";

import type { LayoutNode } from "@/lib/sequence-layout";
import { fmtDuration } from "@/lib/format";

export function ExpandedFrameBody({ layout }: { layout: LayoutNode }) {
  const { label, span } = layout;
  return (
    <div data-expanded-body className="text-[11px] text-warm-fog/70">
      <span className="font-mono">{label}</span>
      {span?.duration_ms != null ? (
        <span className="ml-2 font-mono text-warm-fog/50">
          · {fmtDuration(span.duration_ms)}
        </span>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 6: Implement FlatNodeExpanded**

`web/components/graph/flat-node-expanded.tsx`:

```tsx
"use client";

import type { NodeProps, Node } from "@xyflow/react";
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
          <span
            className="min-w-[16px] h-[16px] px-1 rounded-full bg-peach-neon text-carbon text-[9px] font-bold flex items-center justify-center"
          >
            {commentCount}
          </span>
        ) : null}
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {kind === "llm" ? <ExpandedLlmBody span={span} /> : null}
        {kind === "tool" ? <ExpandedToolBody span={span} /> : null}
        {kind !== "llm" && kind !== "tool" ? (
          <pre className="font-mono text-[10px] text-warm-fog/70 whitespace-pre-wrap break-words">
            {JSON.stringify(span.attributes, null, 2).slice(0, 400)}
          </pre>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Dispatch between compact and expanded in trajectory-graph**

In `web/components/trajectory-graph.tsx`, change the step node type dispatch. Import:

```tsx
import { FlatNodeExpanded } from "@/components/graph/flat-node-expanded";
```

Update the node types map:

```tsx
const nodeTypes = {
  step: FlatNodeCompact,
  stepExpanded: FlatNodeExpanded,
  frame: FrameNodeComp,
};
```

Inside the `useMemo` that builds `rfNodes`, switch the node type based on expand state. First, pull state:

```tsx
const { expandAll, expandedIds, toggleExpand } = useFullscreen();
```

Then when mapping step nodes:

```tsx
const isExpanded =
  ln.kind === "step" &&
  !!ln.span &&
  (expandAll || expandedIds.has(ln.span.span_id));

const type =
  ln.kind === "frame"
    ? "frame"
    : isExpanded
    ? "stepExpanded"
    : "step";

const height = isExpanded ? 320 : ln.height;

return {
  id: ln.id,
  type,
  position: { x: ln.x, y: ln.y },
  parentId: ln.parentId ?? undefined,
  extent: ln.parentId ? ("parent" as const) : undefined,
  draggable: false,
  selectable: ln.kind === "step",
  style: { width: ln.width, height },
  data: {
    layout: ln,
    selected: ln.span?.span_id === selectedId,
    commentCount: 0, // wired in Task 7
    onToggle: () => ln.span && toggleExpand(ln.span.span_id),
  } as unknown as FlatStepData,
  zIndex: ln.kind === "frame"
    ? (ln.frameKind === "parallel" ? 1 : 0)
    : 10,
};
```

Update the `useMemo` dependency array to include `expandAll, expandedIds, toggleExpand`.

- [ ] **Step 8: Run Playwright, expect pass**

```bash
cd web && npx playwright test graph-expanded.spec.ts --project=chromium
```

Expected: both tests PASS.

- [ ] **Step 9: Commit**

```bash
git add web/components/graph/expanded-tool-body.tsx \
        web/components/graph/expanded-llm-body.tsx \
        web/components/graph/expanded-frame-body.tsx \
        web/components/graph/flat-node-expanded.tsx \
        web/components/trajectory-graph.tsx \
        web/tests/graph-expanded.spec.ts
git commit -m "feat(graph): click-to-expand node bodies (tool args/out, llm messages)"
```

---

## Task 5: Resizable sidebar wrapper + tab strip

**Files:**
- Create: `web/components/sidebar/resizable-sidebar.tsx`
- Create: `web/components/sidebar/sidebar-tabs.tsx`
- Modify: `web/components/node-detail-panel.tsx` — wrap in `ResizableSidebar`, restructure around tabs
- Modify: `web/components/trajectory-view.tsx:122-124` — drop the fixed `w-[480px]` container (the sidebar owns its width now)
- Test: `web/tests/sidebar.spec.ts`

- [ ] **Step 1: Write the failing test**

`web/tests/sidebar.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId } from "./_helpers";

test("sidebar has three tabs and defaults to Detail", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  const sb = page.locator('[data-sidebar-root]');
  await expect(sb).toBeVisible();
  await expect(sb.getByRole("tab", { name: /detail/i })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(sb.getByRole("tab", { name: /notes/i })).toBeVisible();
  await expect(sb.getByRole("tab", { name: /thread/i })).toBeVisible();
});

test("sidebar width persists across reload", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  // Set width via localStorage directly, then reload and verify.
  await page.evaluate(() =>
    localStorage.setItem(
      "langperf.sidebar",
      JSON.stringify({ width: 380, open: true, tab: "detail" }),
    ),
  );
  await page.reload();
  const sb = page.locator('[data-sidebar-root]');
  const width = await sb.evaluate((el) => (el as HTMLElement).offsetWidth);
  expect(Math.round(width)).toBe(380);
});
```

- [ ] **Step 2: Run, expect failure**

```bash
cd web && npx playwright test sidebar.spec.ts --project=chromium
```

- [ ] **Step 3: Implement ResizableSidebar**

`web/components/sidebar/resizable-sidebar.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

const STORAGE_KEY = "langperf.sidebar";
const MIN = 280;
const MAX = 720;
const DEFAULT_WIDTH = 420;

type Persisted = { width: number; open: boolean; tab: string };

function load(): Persisted {
  if (typeof window === "undefined") {
    return { width: DEFAULT_WIDTH, open: true, tab: "detail" };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { width: DEFAULT_WIDTH, open: true, tab: "detail" };
    const parsed = JSON.parse(raw) as Partial<Persisted>;
    return {
      width: clamp(parsed.width ?? DEFAULT_WIDTH, MIN, MAX),
      open: parsed.open ?? true,
      tab: parsed.tab ?? "detail",
    };
  } catch {
    return { width: DEFAULT_WIDTH, open: true, tab: "detail" };
  }
}

function save(state: Persisted) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* private-browsing / quota — ignore */
  }
}

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

export function ResizableSidebar({
  children,
  tab,
  onTabChange,
}: {
  children: ReactNode;
  tab: string;
  onTabChange: (t: string) => void;
}) {
  const [hydrated, setHydrated] = useState(false);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [open, setOpen] = useState(true);
  const draggingRef = useRef(false);

  useEffect(() => {
    const s = load();
    setWidth(s.width);
    setOpen(s.open);
    if (s.tab !== tab) onTabChange(s.tab);
    setHydrated(true);
    // onTabChange intentionally omitted to avoid re-firing
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (hydrated) save({ width, open, tab });
  }, [hydrated, width, open, tab]);

  function onMouseDown(e: React.MouseEvent) {
    e.preventDefault();
    draggingRef.current = true;
    const startX = e.clientX;
    const startW = width;
    const move = (ev: MouseEvent) => {
      if (!draggingRef.current) return;
      const delta = startX - ev.clientX;
      setWidth(clamp(startW + delta, MIN, MAX));
    };
    const up = () => {
      draggingRef.current = false;
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  if (!open) {
    return (
      <div
        data-sidebar-root
        data-open="false"
        className="relative flex-shrink-0 border-l border-[color:var(--border)] bg-[color:var(--surface-2)]"
        style={{ width: 24 }}
      >
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Expand sidebar"
          aria-label="Expand sidebar"
          className="w-full h-8 flex items-center justify-center text-[color:var(--muted)] hover:text-warm-fog"
        >
          ‹
        </button>
      </div>
    );
  }

  return (
    <div
      data-sidebar-root
      data-open="true"
      className="relative flex-shrink-0 border-l border-[color:var(--border)] overflow-hidden"
      style={{ width }}
    >
      <div
        onMouseDown={onMouseDown}
        title="Drag to resize"
        className="absolute top-0 left-0 h-full w-1.5 cursor-col-resize z-10 hover:bg-aether-teal/30"
      />
      <button
        type="button"
        onClick={() => setOpen(false)}
        title="Collapse sidebar"
        aria-label="Collapse sidebar"
        className="absolute top-2 left-1.5 z-20 w-5 h-5 flex items-center justify-center text-[10px] text-[color:var(--muted)] hover:text-warm-fog bg-[color:var(--surface)] border border-[color:var(--border)] rounded"
      >
        ›
      </button>
      <div className="h-full pl-2">{children}</div>
    </div>
  );
}
```

- [ ] **Step 4: Implement SidebarTabs**

`web/components/sidebar/sidebar-tabs.tsx`:

```tsx
"use client";

import { type ReactNode } from "react";

export type TabId = "detail" | "notes" | "thread";
export type TabDef = { id: TabId; label: string; badge?: number };

export function SidebarTabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef[];
  active: TabId;
  onChange: (id: TabId) => void;
}) {
  return (
    <div
      role="tablist"
      className="flex border-b border-[color:var(--border)]"
    >
      {tabs.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t.id)}
            className={`flex-1 px-3 py-2 text-[10px] uppercase tracking-wider font-mono transition-colors ${
              isActive
                ? "text-aether-teal border-b-2 border-aether-teal"
                : "text-warm-fog/60 hover:text-warm-fog border-b-2 border-transparent"
            }`}
          >
            {t.label}
            {t.badge != null && t.badge > 0 ? (
              <span className="ml-1.5 inline-block min-w-[14px] h-[14px] px-1 rounded-full bg-peach-neon text-carbon text-[8px] font-bold leading-[14px]">
                {t.badge}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

export function TabPane({ active, children }: { active: boolean; children: ReactNode }) {
  if (!active) return null;
  return <div className="h-full overflow-y-auto">{children}</div>;
}
```

- [ ] **Step 5: Refactor node-detail-panel**

Replace `web/components/node-detail-panel.tsx` entirely:

```tsx
"use client";

import { useState } from "react";
import type { Span, TrajectoryDetail } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { GenericSpanView } from "@/components/views/generic-span-view";
import { LlmSpanView } from "@/components/views/llm-span-view";
import { ToolSpanView } from "@/components/views/tool-span-view";
import { NotesEditor } from "@/components/notes-editor";
import { useSelection } from "@/components/selection-context";
import {
  ResizableSidebar,
} from "@/components/sidebar/resizable-sidebar";
import {
  SidebarTabs,
  TabPane,
  type TabId,
} from "@/components/sidebar/sidebar-tabs";

export function NodeDetailPanel({ trajectory }: { trajectory?: TrajectoryDetail }) {
  const { selectedSpan: span, select, clear } = useSelection();
  const [tab, setTab] = useState<TabId>("detail");

  return (
    <ResizableSidebar tab={tab} onTabChange={(t) => setTab(t as TabId)}>
      <div className="h-full flex flex-col">
        <header className="border-b border-[color:var(--border)] px-5 pl-6 py-3 flex-shrink-0">
          {span ? (
            <>
              <div className="flex items-center justify-between">
                <div className="text-[10px] uppercase tracking-wider text-[color:var(--muted)]">
                  {kindOf(span)}
                </div>
                {trajectory ? (
                  <button
                    type="button"
                    onClick={clear}
                    className="text-[10px] text-[color:var(--muted)] hover:text-[color:var(--foreground)] border border-[color:var(--border)] rounded px-2 py-0.5"
                    title="View all notes in this run"
                  >
                    all notes
                  </button>
                ) : null}
              </div>
              <div className="text-sm font-medium mt-0.5 truncate">{span.name}</div>
              <div className="text-[10px] font-mono text-[color:var(--muted)] mt-1">
                {span.span_id}
              </div>
            </>
          ) : (
            <>
              <div className="text-[10px] uppercase tracking-wider text-[color:var(--muted)]">
                run
              </div>
              <div className="text-sm font-medium mt-0.5 truncate">
                {trajectory?.name ?? "(unnamed run)"}
              </div>
            </>
          )}
        </header>

        <SidebarTabs
          active={tab}
          onChange={setTab}
          tabs={[
            { id: "detail", label: "Detail" },
            { id: "notes", label: "Notes" },
            { id: "thread", label: "Thread" },
          ]}
        />

        <div className="flex-1 min-h-0">
          <TabPane active={tab === "detail"}>
            <DetailTab span={span} />
          </TabPane>
          <TabPane active={tab === "notes"}>
            <NotesTab span={span} trajectory={trajectory} onSelect={(s) => select(s)} />
          </TabPane>
          <TabPane active={tab === "thread"}>
            <ThreadTab span={span} trajectory={trajectory} />
          </TabPane>
        </div>
      </div>
    </ResizableSidebar>
  );
}

function DetailTab({ span }: { span: Span | null }) {
  if (!span) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Select a node in the graph or tree to see its detail.
      </div>
    );
  }
  const kind = kindOf(span);
  return (
    <div className="p-5">
      {kind === "llm" ? <LlmSpanView span={span} /> : null}
      {kind === "tool" ? <ToolSpanView span={span} /> : null}
      {kind !== "llm" && kind !== "tool" ? <GenericSpanView span={span} /> : null}
    </div>
  );
}

function NotesTab({
  span,
  trajectory,
  onSelect,
}: {
  span: Span | null;
  trajectory?: TrajectoryDetail;
  onSelect: (s: Span) => void;
}) {
  if (span) {
    return (
      <div className="p-5">
        <NotesEditor
          key={span.span_id}
          target={{ kind: "node", id: span.span_id }}
          value={span.notes}
          placeholder="Notes on this node…"
          compact
        />
      </div>
    );
  }
  if (!trajectory) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Select a node to add notes.
      </div>
    );
  }
  const annotated = trajectory.spans.filter(
    (s) => (s.notes ?? "").trim() !== "",
  );
  const trajectoryHasNote = (trajectory.notes ?? "").trim() !== "";
  return (
    <div className="p-5 space-y-4">
      <NotesEditor
        target={{ kind: "trajectory", id: trajectory.id }}
        value={trajectory.notes}
        placeholder="Notes on this run…"
        compact
      />
      {annotated.length === 0 && !trajectoryHasNote ? (
        <p className="text-xs text-[color:var(--muted)] italic">
          Per-node notes show up here once you add them.
        </p>
      ) : (
        annotated.map((s) => (
          <button
            key={s.span_id}
            type="button"
            onClick={() => onSelect(s)}
            className="w-full text-left rounded border border-[color:var(--border)] bg-[color:var(--surface-2)] p-3 hover:border-aether-teal/60"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-wider text-[color:var(--muted)]">
                {kindOf(s).toUpperCase()}
              </span>
              <span className="text-xs font-medium truncate">{s.name}</span>
            </div>
            <div className="text-xs whitespace-pre-wrap">{s.notes}</div>
          </button>
        ))
      )}
    </div>
  );
}

function ThreadTab({
  span,
  trajectory,
}: {
  span: Span | null;
  trajectory?: TrajectoryDetail;
}) {
  return (
    <div className="p-5 text-sm text-[color:var(--muted)]">
      {span || trajectory
        ? /* Wired in Task 6 */ null
        : "Select a node to join the conversation."}
      {/* placeholder until Task 6 wires in NodeThread */}
    </div>
  );
}
```

- [ ] **Step 6: Update trajectory-view to drop the fixed-width container**

Edit `web/components/trajectory-view.tsx` lines 122–124. Replace:

```tsx
<div className="w-[480px] flex-shrink-0 overflow-hidden">
  <NodeDetailPanel trajectory={trajectory} />
</div>
```

with:

```tsx
<NodeDetailPanel trajectory={trajectory} />
```

- [ ] **Step 7: Run Playwright, expect pass**

```bash
cd web && npx playwright test sidebar.spec.ts --project=chromium
```

Expected: both tests PASS.

- [ ] **Step 8: Commit**

```bash
git add web/components/sidebar/resizable-sidebar.tsx \
        web/components/sidebar/sidebar-tabs.tsx \
        web/components/node-detail-panel.tsx \
        web/components/trajectory-view.tsx \
        web/tests/sidebar.spec.ts
git commit -m "feat(sidebar): resizable + collapsible with Detail/Notes/Thread tabs"
```

---

## Task 6: Per-node thread + comment counts

**Files:**
- Create: `web/lib/comment-counts.ts`
- Create: `web/components/collab/node-thread.tsx`
- Modify: `web/components/node-detail-panel.tsx:ThreadTab` — use `NodeThread`
- Modify: `web/components/trajectory-graph.tsx` — wire comment counts into node data
- Test: `web/tests/graph-comments.spec.ts`

- [ ] **Step 1: Write the failing test**

`web/tests/graph-comments.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId, firstSpanId } from "./_helpers";

test("node shows comment dot after posting a thread comment", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  const spanId = await firstSpanId(request, tid);

  // Post a comment directly via API
  await request.post(`/api/trajectories/${tid}/nodes/${spanId}/comments`, {
    data: { body: "smoke thread comment" },
  });

  await page.goto(`/t/${tid}`);
  const node = page
    .locator('[data-node-kind]')
    .first();
  const badge = node.locator('[aria-label*="comment"]');
  await expect(badge).toBeVisible();
});

test("sidebar Thread tab lists posted comments", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  const spanId = await firstSpanId(request, tid);
  await request.post(`/api/trajectories/${tid}/nodes/${spanId}/comments`, {
    data: { body: "hello thread" },
  });

  await page.goto(`/t/${tid}`);
  await page.getByRole("tab", { name: /thread/i }).click();
  await expect(page.getByText("hello thread")).toBeVisible();
});
```

Extend `web/tests/_helpers.ts` with:

```ts
export async function firstSpanId(
  request: APIRequestContext,
  trajectoryId: string,
): Promise<string> {
  const r = await request.get(`/api/trajectories/${trajectoryId}`);
  const body = await r.json();
  return body.spans[0].span_id;
}
```

- [ ] **Step 2: Run, expect failure** (no comment badge, no Thread tab content)

```bash
cd web && npx playwright test graph-comments.spec.ts --project=chromium
```

- [ ] **Step 3: Implement comment-counts lib**

`web/lib/comment-counts.ts`:

```ts
"use client";

import { useEffect, useState } from "react";
import type { TrajectoryDetail } from "./api";
import { listComments } from "./collab";

/**
 * Fetches comment counts per span for the given trajectory. Issues one
 * request per span in parallel — simple v1, good enough at dogfood scale.
 * For larger trajectories a single `?include=counts` endpoint is a v-next
 * optimization.
 */
export function useCommentCounts(
  trajectory: TrajectoryDetail | undefined,
): Map<string, number> {
  const [counts, setCounts] = useState<Map<string, number>>(new Map());

  useEffect(() => {
    if (!trajectory) return;
    let cancelled = false;
    const ids = trajectory.spans.map((s) => s.span_id);
    Promise.all(
      ids.map(async (spanId) => {
        try {
          const rows = await listComments(trajectory.id, spanId);
          return [spanId, rows.length] as const;
        } catch {
          return [spanId, 0] as const;
        }
      }),
    ).then((pairs) => {
      if (cancelled) return;
      const next = new Map<string, number>();
      for (const [id, n] of pairs) if (n > 0) next.set(id, n);
      setCounts(next);
    });
    return () => {
      cancelled = true;
    };
  }, [trajectory]);

  return counts;
}
```

- [ ] **Step 4: Implement NodeThread**

`web/components/collab/node-thread.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { createComment, listComments, type Comment } from "@/lib/collab";
import { CommentThread } from "@/components/collab/comment-thread";
import { CommentComposer } from "@/components/collab/comment-composer";

export function NodeThread({
  trajectoryId,
  spanId,
}: {
  trajectoryId: string;
  spanId: string | null;
}) {
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setComments(null);
    setErr(null);
    if (!spanId) return;
    let cancelled = false;
    listComments(trajectoryId, spanId)
      .then((rows) => {
        if (!cancelled) setComments(rows);
      })
      .catch((e) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : "error");
      });
    return () => {
      cancelled = true;
    };
  }, [trajectoryId, spanId]);

  async function onSubmit(body: string) {
    if (!spanId) return;
    await createComment(trajectoryId, spanId, body);
    const rows = await listComments(trajectoryId, spanId);
    setComments(rows);
  }

  if (!spanId) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Select a node to join the conversation.
      </div>
    );
  }

  if (err) {
    return (
      <div className="p-6 text-sm text-warn">
        Failed to load thread: {err}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto p-4">
        {comments && comments.length > 0 ? (
          <CommentThread comments={comments} />
        ) : comments ? (
          <p className="text-xs text-[color:var(--muted)] italic">
            No comments yet — use the composer below.
          </p>
        ) : (
          <p className="text-xs text-[color:var(--muted)]">Loading…</p>
        )}
      </div>
      <div className="flex-shrink-0 border-t border-[color:var(--border)] p-3">
        <CommentComposer onSubmit={onSubmit} />
      </div>
    </div>
  );
}
```

> **Note:** this assumes `CommentThread` accepts `comments: Comment[]` as a prop. Inspect `web/components/collab/comment-thread.tsx`; if it expects `trajectoryId + spanId` and fetches internally, swap to that signature — pass `{trajectoryId, spanId}` and drop the local state. Keep NodeThread thin.

- [ ] **Step 5: Wire NodeThread into node-detail-panel**

Edit the `ThreadTab` function in `web/components/node-detail-panel.tsx`:

```tsx
function ThreadTab({
  span,
  trajectory,
}: {
  span: Span | null;
  trajectory?: TrajectoryDetail;
}) {
  if (!trajectory) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Loading trajectory…
      </div>
    );
  }
  return (
    <NodeThread
      trajectoryId={trajectory.id}
      spanId={span ? span.span_id : null}
    />
  );
}
```

Add import:

```tsx
import { NodeThread } from "@/components/collab/node-thread";
```

- [ ] **Step 6: Pipe comment counts through to graph**

Edit `web/components/trajectory-view.tsx`:

```tsx
import { useCommentCounts } from "@/lib/comment-counts";
// inside the component, after SelectionProvider wrapping:
const commentCounts = useCommentCounts(trajectory);
```

Pass to the graph:

```tsx
<TrajectoryGraph spans={trajectory.spans} commentCounts={commentCounts} />
```

Update `web/components/trajectory-graph.tsx` signature:

```tsx
export function TrajectoryGraph({
  spans,
  commentCounts,
}: {
  spans: Span[];
  commentCounts?: Map<string, number>;
}) {
  // ...existing code
  // In rfNodes mapping, change commentCount: 0 to:
  commentCount: ln.span ? commentCounts?.get(ln.span.span_id) ?? 0 : 0,
}
```

Add to the memo deps: `commentCounts`.

Update `web/components/trajectory-timeline.tsx` if it accepts the same prop; otherwise leave it.

- [ ] **Step 7: Run Playwright, expect pass**

```bash
cd web && npx playwright test graph-comments.spec.ts --project=chromium
```

Expected: both tests PASS.

- [ ] **Step 8: Commit**

```bash
git add web/lib/comment-counts.ts \
        web/components/collab/node-thread.tsx \
        web/components/node-detail-panel.tsx \
        web/components/trajectory-view.tsx \
        web/components/trajectory-graph.tsx \
        web/tests/graph-comments.spec.ts \
        web/tests/_helpers.ts
git commit -m "feat(graph): per-node threads in sidebar + comment-count badges on nodes"
```

---

## Task 7: Floating inspector + full-screen layout

**Files:**
- Create: `web/components/graph/floating-inspector.tsx`
- Modify: `web/components/trajectory-view.tsx` — switch layout when `fsOpen`
- Modify: `web/components/trajectory-graph.tsx` — render `FloatingInspector` when `fsOpen && span`
- Test: `web/tests/graph-fullscreen.spec.ts`

- [ ] **Step 1: Write the failing test**

`web/tests/graph-fullscreen.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId } from "./_helpers";

test("F key toggles full-screen; tree collapses to rail", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);

  await page.keyboard.press("f");
  await expect(page.locator('[data-fs="1"]')).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.locator('[data-fs="0"]')).toBeVisible();
});

test("floating inspector appears when a node is selected in fullscreen", async ({
  page,
  request,
}) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}?fs=1`);

  await page.locator('[data-node-kind]').first().click();
  await expect(page.locator('[data-floating-inspector]')).toBeVisible();
});
```

- [ ] **Step 2: Run, expect failure**

```bash
cd web && npx playwright test graph-fullscreen.spec.ts --project=chromium
```

- [ ] **Step 3: Implement FloatingInspector**

`web/components/graph/floating-inspector.tsx`:

```tsx
"use client";

import { useSelection } from "@/components/selection-context";
import { kindOf, extractToolFields, extractLlmFields } from "@/lib/span-fields";
import { fmtDuration } from "@/lib/format";

export function FloatingInspector({
  onOpenFull,
}: {
  onOpenFull: () => void;
}) {
  const { selectedSpan: span } = useSelection();
  if (!span) return null;

  const kind = kindOf(span);

  return (
    <div
      data-floating-inspector=""
      className="absolute bottom-3 right-3 w-[260px] rounded-md border shadow-xl p-3 z-20 pointer-events-auto"
      style={{
        background: "var(--surface)",
        borderColor: "var(--border)",
        borderLeftWidth: 3,
        borderLeftColor: kind === "tool" ? "#E8A87C" : "#6BBAB1",
      }}
    >
      <div className="flex items-center gap-2 text-[9px] uppercase tracking-wider text-warm-fog/60">
        <span>{kind}</span>
        <span className="text-warm-fog/90 font-medium normal-case text-[11px] tracking-normal truncate">
          {span.name}
        </span>
        <span className="ml-auto font-mono">{fmtDuration(span.duration_ms)}</span>
      </div>
      <div className="mt-2 space-y-1 font-mono text-[10px] text-warm-fog/90 break-words">
        {kind === "tool" ? <ToolPreview span={span} /> : null}
        {kind === "llm" ? <LlmPreview span={span} /> : null}
      </div>
      <button
        type="button"
        onClick={onOpenFull}
        className="mt-2 text-[10px] text-aether-teal hover:underline"
      >
        open full detail →
      </button>
    </div>
  );
}

function ToolPreview({ span }: { span: import("@/lib/api").Span }) {
  const f = extractToolFields(span.attributes);
  const input = f.input ?? f.parameters ?? null;
  const output = f.output ?? null;
  return (
    <>
      {input != null ? (
        <div>
          <span className="text-warm-fog/50">args</span>{" "}
          {truncate(JSON.stringify(input), 80)}
        </div>
      ) : null}
      {output != null ? (
        <div>
          <span className="text-warm-fog/50">out</span>{" "}
          {truncate(JSON.stringify(output), 80)}
        </div>
      ) : null}
    </>
  );
}

function LlmPreview({ span }: { span: import("@/lib/api").Span }) {
  const f = extractLlmFields(span.attributes);
  const last = f.output_messages[f.output_messages.length - 1];
  const preview = last?.content ?? "(no output)";
  return (
    <div>
      <span className="text-warm-fog/50">out</span> {truncate(preview, 120)}
    </div>
  );
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1) + "…";
}
```

- [ ] **Step 4: Render inspector in graph + switch layouts**

Edit `web/components/trajectory-graph.tsx`:

```tsx
import { FloatingInspector } from "@/components/graph/floating-inspector";
// inside TrajectoryGraph, near top:
const { fsOpen } = useFullscreen();
// ... after <ReactFlow>...</ReactFlow>, inside the wrapping div:
{fsOpen ? (
  <FloatingInspector onOpenFull={() => { /* v1: no-op. v-next: drive sidebar open + tab=detail via `?tab` deep-link. */ }} />
) : null}
```

Edit `web/components/trajectory-view.tsx` to switch layouts based on `fsOpen`. Extract a small internal component since `useFullscreen` requires being inside the provider:

```tsx
import { useFullscreen } from "@/components/graph/fullscreen-context";
// ...
export function TrajectoryView({ trajectory }: { trajectory: TrajectoryDetail }) {
  const firstSpanId = trajectory.spans[0]?.span_id ?? null;
  return (
    <SelectionProvider spans={trajectory.spans} initialId={firstSpanId}>
      <FullscreenProvider>
        <TrajectoryLayout trajectory={trajectory} />
      </FullscreenProvider>
    </SelectionProvider>
  );
}

function TrajectoryLayout({ trajectory }: { trajectory: TrajectoryDetail }) {
  const { fsOpen } = useFullscreen();
  const commentCounts = useCommentCounts(trajectory);
  return (
    <div data-fs={fsOpen ? "1" : "0"} className="h-screen flex flex-col">
      {/* existing header minus the lower toggles when fsOpen (optional; can keep as-is for v1) */}
      {/* body: if fsOpen, drop tree pane; otherwise the existing split */}
      {fsOpen ? (
        <div className="flex flex-1 overflow-hidden">
          <div className="flex-1 min-w-0">
            <TrajectoryGraph
              spans={trajectory.spans}
              commentCounts={commentCounts}
            />
          </div>
          <NodeDetailPanel trajectory={trajectory} />
        </div>
      ) : (
        /* existing split layout — tree on top of main, graph/timeline below, sidebar right */
        // use whatever was there before; paste it here and point the graph to commentCounts.
      )}
    </div>
  );
}
```

Concrete: keep the existing header + split layout exactly as it was, but also add the `data-fs` attribute at the root and introduce the `fsOpen` branch around body-panel composition. The previous body JSX lives inside the `else` branch unchanged except the graph now receives `commentCounts`.

- [ ] **Step 5: Handle keyboard shortcuts**

Add at the top of `TrajectoryLayout`:

```tsx
import { useEffect } from "react";
const { fsOpen, toggleFs, toggleExpandAll, collapseAll } = useFullscreen();

useEffect(() => {
  const onKey = (e: KeyboardEvent) => {
    // Ignore when typing in an input, textarea, or contentEditable.
    const target = e.target as HTMLElement | null;
    if (
      target &&
      (target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable)
    ) return;
    if (e.key === "f" || e.key === "F") toggleFs();
    else if (e.key === "Escape" && fsOpen) toggleFs();
    else if (e.key === "e" || e.key === "E") toggleExpandAll();
    else if (e.key === "c" || e.key === "C") collapseAll();
  };
  window.addEventListener("keydown", onKey);
  return () => window.removeEventListener("keydown", onKey);
}, [fsOpen, toggleFs, toggleExpandAll, collapseAll]);
```

- [ ] **Step 6: Run Playwright, expect pass**

```bash
cd web && npx playwright test graph-fullscreen.spec.ts --project=chromium
```

Expected: both tests PASS.

- [ ] **Step 7: Commit**

```bash
git add web/components/graph/floating-inspector.tsx \
        web/components/trajectory-view.tsx \
        web/components/trajectory-graph.tsx \
        web/tests/graph-fullscreen.spec.ts
git commit -m "feat(graph): full-screen mode + floating inspector + keyboard shortcuts"
```

---

## Task 8: URL parameter sync + deep links

**Files:**
- Modify: `web/components/trajectory-view.tsx` — read `?fs` and `?span` on mount, push state on toggle
- Test: `web/tests/graph-deeplink.spec.ts`

- [ ] **Step 1: Write the failing test**

`web/tests/graph-deeplink.spec.ts`:

```ts
import { test, expect } from "@playwright/test";
import { bootstrapAdmin, firstTrajectoryId } from "./_helpers";

test("?fs=1 opens in full-screen mode", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}?fs=1`);
  await expect(page.locator('[data-fs="1"]')).toBeVisible();
});

test("toggling full-screen updates URL", async ({ page, request }) => {
  await bootstrapAdmin(request);
  const tid = await firstTrajectoryId(request);
  await page.goto(`/t/${tid}`);
  await page.keyboard.press("f");
  await expect(page).toHaveURL(/fs=1/);
  await page.keyboard.press("Escape");
  await expect(page).not.toHaveURL(/fs=1/);
});
```

- [ ] **Step 2: Run, expect failure**

```bash
cd web && npx playwright test graph-deeplink.spec.ts --project=chromium
```

- [ ] **Step 3: Hydrate from URL + push on toggle**

Edit `TrajectoryLayout` in `web/components/trajectory-view.tsx`:

```tsx
"use client";
import { useEffect } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";

// inside the component:
const router = useRouter();
const pathname = usePathname();
const params = useSearchParams();
const { fsOpen, toggleFs, setFs } = useFullscreen();

// On mount, sync fsOpen to URL
useEffect(() => {
  const want = params.get("fs") === "1";
  if (want !== fsOpen) setFs(want);
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, []);

// When fsOpen changes, push URL
useEffect(() => {
  const want = fsOpen ? "1" : null;
  const current = params.get("fs");
  if (current !== want) {
    const sp = new URLSearchParams(params.toString());
    if (want) sp.set("fs", want);
    else sp.delete("fs");
    const q = sp.toString();
    router.replace(q ? `${pathname}?${q}` : pathname);
  }
}, [fsOpen, params, router, pathname]);
```

(The selected-span sync `?span=<id>` is optional polish; leave for a follow-up to keep this task tight.)

- [ ] **Step 4: Run Playwright, expect pass**

```bash
cd web && npx playwright test graph-deeplink.spec.ts --project=chromium
```

Expected: both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add web/components/trajectory-view.tsx web/tests/graph-deeplink.spec.ts
git commit -m "feat(graph): URL param sync for ?fs=1 (shareable full-screen link)"
```

---

## Task 9: Manual smoke + tidy

**No code changes unless the smoke surfaces bugs.** This task is a checkpoint against the live docker compose stack.

- [ ] **Step 1: Confirm docker compose services are healthy**

```bash
docker compose ps
```

Both `langperf-api` and `langperf-web` must be `Up`.

- [ ] **Step 2: Manual smoke against a real trajectory**

In your browser:

1. Open `/agents`, register `smoke-graph` if you don't have one; copy the token.
2. Emit a short trace:

```bash
LANGPERF_API_TOKEN=<token> .venv/bin/python - <<'PY'
import langperf, time
from opentelemetry import trace
langperf.init(endpoint="http://localhost:4318", service_name="smoke-graph", environment="dev", api_token="<token>")
tracer = trace.get_tracer("smoke")
with tracer.start_as_current_span("root") as root:
    root.set_attribute("gen_ai.system", "openai")
    with tracer.start_as_current_span("bash") as t:
        t.set_attribute("tool.name", "bash")
        t.set_attribute("tool.arguments", '{"cmd":"echo hi"}')
        t.set_attribute("tool.output", '"hi\n"')
time.sleep(2)
PY
```

3. Open `/t/<trajectory_id>`. Confirm:
   - No gradients on any node.
   - Labelled edge between the LLM and the bash tool (`tool:bash`).
   - Click the bash node → inline ARGS IN / RESULT OUT appear.
   - Click an edge label → payload peek reveals the first ~50 chars.
   - Click "expand all" toolbar → every node shows a body.
   - Press `F` → full-screen; tree collapses to rail; URL has `?fs=1`.
   - Floating inspector appears on select in full-screen.
   - Press `Esc` → back to split; URL loses `?fs=1`.
   - Sidebar tabs: Detail / Notes / Thread visible. Notes aggregate visible when no span selected.
   - Post a comment in Thread tab → comment count dot appears on the node.
   - Drag sidebar left edge → width persists on reload.

- [ ] **Step 3: Tidy any eyeball issues**

If any of the above looks wrong, commit small fixes with messages of the form `fix(graph): <what>`.

- [ ] **Step 4: Run full Playwright suite**

```bash
cd web && npx playwright test --project=chromium
```

Expected: all tests pass, no regressions in pre-existing specs.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "chore(graph): smoke polish from manual test"
```

If nothing changed, skip this step.

---

## Done

After Task 9, the plan is complete. You have:

- Flat nodes (no gradients) with a single kind stripe and comment-count badge.
- Labelled edges connecting sibling spans, click-to-reveal JSON peek.
- Expand-on-click inline bodies for tool and LLM nodes; expand-all/compact-all toolbar toggles.
- Resizable, collapsible sidebar with Detail / Notes / Thread tabs. Width persists in localStorage.
- Per-node comment threads wired to v2b backend; `@name` mentions fire notifications.
- Full-screen mode with keyboard shortcuts (`F`, `Esc`, `E`, `C`) and a floating inspector.
- `?fs=1` URL parameter for shareable full-screen deep links.

Follow-ups captured but not in scope:
- `?span=<id>` URL hydration + `?tab=thread` deep link.
- `?tab=detail` and the floating inspector's "open full detail →" link actually opening the sidebar to that tab.
- `j/k` keyboard navigation across nodes.
- `/` search focus.
- Single backend endpoint for per-trajectory comment counts (replaces the N-request fan-out in `useCommentCounts`).
- Tree pane click-to-overlay in full-screen mode (spec called this; plan currently drops the tree entirely in fs — the 24px rail is a placeholder that does nothing on click).
- Slim run-header strip in full-screen (spec detail; plan keeps the current header as-is in fs).
- Backend comment counts aggregate endpoint to replace the N-request fan-out.
