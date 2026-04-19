# Trajectory Graph Redesign — Design Spec

**Date:** 2026-04-19
**Author:** Andrew + brainstorming session
**Status:** Ready for implementation planning
**Visual companion session:** `.superpowers/brainstorm/23948-1776614625/content/` (node-density, edges, expanded-body, fullscreen, sidebar-comments)

## Goals

Make the trajectory graph the primary lens on "what did this agent actually do." Concretely:

1. **Flatter visual style.** No gradients, solid fills with a single accent stripe per kind, one-weight borders.
2. **Visible data flow.** Edges with short semantic labels (`tool:bash`, `return`, `message`) — click an edge to reveal a truncated payload peek.
3. **Inline input/output on nodes.** Compact by default; click a node to expand inline; global expand-all / compact-all toggle.
4. **Full-screen mode.** Graph becomes the whole viewport below the app top bar. Floating inspector + resizable sidebar preserve access to detail and conversation.
5. **Per-node comment threads.** Google-Doc-style threaded comments with `@mentions`, surfaced in a sidebar tab and indicated on nodes via a dot badge.

## Non-goals

- Changing the ingest pipeline, span shape, or the `buildSequenceLayout` algorithm.
- Replacing React Flow (`@xyflow/react`).
- Changing the tree or timeline panes beyond what's needed for full-screen integration.
- Adding new comment / mention / notification backend — v2b already supplies all of it.
- Redesigning trajectory metadata header, tag selector, or trajectory-level notes button.
- New layout engine, new physics, or auto-flow diagrams. Sequence layout stays.
- `/` search, `j/k` keyboard navigation (noted as v-next).

## Architecture overview

The redesign is additive rendering + new state; no schema changes, no API changes. High-level structure:

- **React Flow host** unchanged: same viewport, same pan/zoom, same `Controls`, same dot background.
- **Custom node renderers** (`flat-node-compact`, `flat-node-expanded`, split by span kind).
- **Custom edge renderer** (`labelled-edge`) — new, since the current graph renders zero edges.
- **Graph-level state** (`fullscreen-context`) holds: `fsOpen`, `toggleFs`, global `expandAll: boolean`, per-span `expandedIds: Set<string>`, plus toggle actions.
- **Sidebar** becomes a resizable, collapsible, tabbed surface with Detail · Notes · Thread. Width + open-tab persist in localStorage per user.
- **Per-node comments** wrap existing v2b `comment-thread` / `comment-composer` components; backend routes are already in place.

## Data flow

1. `TrajectoryDetail` (spans + trajectory metadata + notes) loads on the server as today.
2. Client tree wraps contents in `SelectionProvider` (existing) + `FullscreenContext.Provider` (new).
3. `lib/graph-edges.ts` computes the `Edge[]` array once per `spans[]`, memoized. Edge labels derive from span attributes:
   - LLM span emits a tool call → edge to the tool span labeled `tool:<name>`.
   - Tool span returns → edge to the next LLM span labeled `return`.
   - LLM → LLM sequential transitions → edge labeled `message`.
   - Otherwise → edge with no label (plain sequence).
4. Expand state: `expandAll=true` OR `expandedIds.has(span_id)` → render expanded body. Clicking a node toggles its override.
5. Comments load lazily per `span_id` when the Thread tab opens; cached in a Map for the session; invalidated on send / mention / resolve.
6. Notes remain eagerly loaded (they're already part of the span payload).
7. URL params hydrate on first paint: `?fs=1` → `fsOpen=true`; `?span=<id>` → `SelectionProvider.initialId` override.

## Component layout

### New files

| Path | Responsibility |
|---|---|
| `web/components/graph/flat-node-compact.tsx` | Single-line node: kind badge, title, tokens, duration, comment-dot. Default state. |
| `web/components/graph/flat-node-expanded.tsx` | Expanded card shell; dispatches on `kindOf(span)` to the three body variants. |
| `web/components/graph/expanded-tool-body.tsx` | `args in` + `result out` blocks. ~200-char truncation. "Show more" opens sidebar. |
| `web/components/graph/expanded-llm-body.tsx` | Role-chipped input messages, output with tool calls, model/tokens footer strip. |
| `web/components/graph/expanded-frame-body.tsx` | Minimal (label + span count + total duration). Frames do not expand-on-click; shown in expand-all only. |
| `web/components/graph/labelled-edge.tsx` | React Flow custom edge: line + label chip. Click chip → expand in place to show truncated JSON. |
| `web/components/graph/graph-toolbar.tsx` | Top-right toolbar inside the graph pane: expand-all / compact-all / full-screen. Buttons double as keyboard-shortcut hints. |
| `web/components/graph/floating-inspector.tsx` | Bottom-right dock card shown in full-screen when a span is selected; shows kind + duration + args + out + "open full detail →" link to sidebar Detail tab. |
| `web/components/graph/fullscreen-context.tsx` | Provider for `fsOpen`, `toggleFs`, `expandAll`, `toggleExpandAll`, `expandedIds`, `toggleExpand(id)`. |
| `web/components/sidebar/resizable-sidebar.tsx` | Resizer handle on the left edge; collapse chevron; width + open/closed state persist to localStorage under `langperf.sidebar`. |
| `web/lib/graph-edges.ts` | Pure function: `buildEdges(spans: Span[]): Edge[]`. |
| `web/lib/expand-state.ts` | Hook `useExpandState(spanId)` → `[expanded: boolean, toggle: () => void]`; reads from `FullscreenContext`. |

### Refactored files

| Path | Change |
|---|---|
| `web/components/trajectory-graph.tsx` | Shrinks to a host component: mounts toolbar, supplies `nodeTypes`/`edgeTypes`, wires selection, renders React Flow. |
| `web/components/trajectory-view.tsx` | Mounts `FullscreenContext.Provider`. Chooses between split (tree top + graph bottom + sidebar right) and full-screen (tree collapsed to rail + graph + floating inspector + sidebar) based on `fsOpen`. URL sync for `?fs=1` and `?span=<id>`. |
| `web/components/node-detail-panel.tsx` | Becomes a tabbed panel inside `ResizableSidebar`: `Detail` · `Notes` · `Thread`. Detail wraps the existing LLM/Tool/Generic span views. Notes wraps existing `NotesEditor`. Thread wraps v2b `CommentThread` / `CommentComposer`. |

No renames or deletes. Existing consumers (trajectory-view, sidebar, tree) keep their external contracts.

## Visual rules (flat style)

**Baseline:**
- Surface: `var(--surface)` (solid; no alpha, no gradient).
- Border: `1px solid var(--border)`.
- Accent stripe: `3px` left border in kind color — teal for LLM, peach-neon for tool, patina for generic/frame.
- Text: `var(--foreground)` for titles, `var(--muted)` for labels, monospace for identifiers and payloads.

**Selected state:**
- Border swaps to `var(--accent)` (teal).
- Outer ring `2px solid var(--accent)` at 25% alpha.
- No drop shadow on nodes.

**Error state:**
- Left accent stripe becomes `var(--warn)`.
- Small `!` glyph top-right.

**Edges:**
- Line: `1px solid var(--border-strong)`.
- Arrowhead: same color, 8px.
- Label chip: `var(--surface)` bg + `1px solid var(--border)`, 9px uppercase tracking, muted color.
- Click the chip → it grows to reveal ~50 chars of pretty-printed JSON; click again collapses.

**Floating inspector (full-screen only):**
- Keep drop shadow (this is a genuine overlay and needs lift off the canvas).
- 240px wide, docked bottom-right, 12px inset.
- Small × close button. Closing does not clear selection.

**Background:**
- Dot pattern stays as-is (already flat).

## Node bodies

### Tool (expanded)

```
┌──────────────────────────────────────────┐
│ [tool] bash              2ms  ok         │
├──────────────────────────────────────────┤
│ ARGS IN                                   │
│ { "cmd": "echo hello" }                   │
│                                            │
│ RESULT OUT                                │
│ "hello\n"                                  │
└──────────────────────────────────────────┘
```

- `args in` block: `f.input ?? f.parameters ?? span.attributes`, pretty-printed JSON, max 200 chars; "show more" link opens sidebar Detail tab.
- `result out` block: `f.output`, same rules. Omitted entirely if output is null/undefined.
- Block container: `1px solid var(--border)`, `var(--carbon)` bg, 6px 8px padding.

### LLM (expanded)

```
┌──────────────────────────────────────────┐
│ [llm] ChatCompletion    317t  1.09s      │
├──────────────────────────────────────────┤
│ INPUT                                      │
│ [sys] You are a concise assistant…        │
│ [usr] Use the bash tool to run: echo…     │
│                                            │
│ OUTPUT                                     │
│ [asst] I'll run that for you.             │
│ → bash({"cmd":"echo hello"})              │
├──────────────────────────────────────────┤
│ prompt 311t · compl 6t · google/gemma-4   │
└──────────────────────────────────────────┘
```

- One line per input/output message. Role chip (`sys`/`usr`/`asst`/`tool`) + first 120 chars of content, truncated with `…`.
- Tool calls rendered as `→ name(args-truncated)` on their own line, peach-neon color.
- Footer strip: `prompt` · `compl` · `model` with monospace values, muted labels.
- "Show more" on any message link opens sidebar Detail tab to that span with the full message list.

### Frame (expanded — only in expand-all)

- Label + span count + total duration. No nested expansion of child bodies.
- Rendered as a thin banner at the top of the frame rectangle; child step nodes inside still render per their own state.

## Interactions

### Keyboard

- `F` — toggle full-screen.
- `Esc` — exit full-screen if in it; else no-op.
- `E` — expand all nodes.
- `C` — compact all nodes.
- `/` — focus on search (v-next; not this cut).
- `j` / `k` — next / prev node in execution order (v-next; not this cut).

### Mouse

- Click node body → select + toggle per-node expand override.
- Click node title bar → collapse if expanded (redundant with body click, safety exit).
- Click edge chip → toggle the payload peek on that chip only.
- Click floating inspector "open full detail →" → open sidebar (if collapsed) and switch to Detail tab.
- Drag sidebar left edge → resize. Persists.
- Click sidebar chevron → collapse/expand. Persists.
- Shift+Click on empty canvas → clear selection (Detail tab shows aggregate view from previous task).

## Comments (Thread tab)

- Reuses v2b `comment-thread` and `comment-composer` components verbatim; only the wrapper changes.
- Context: `target={{ kind: "node", id: span.span_id }}` when a node is selected; `target={{ kind: "trajectory", id: trajectory.id }}` when the trajectory header is clicked or selection is cleared.
- Thread shape: flat list of top-level comments; each can have a single level of nested replies. No deeper nesting.
- `@name` autocomplete fetches `/api/auth/org/members` once per sidebar open; caches in component state.
- Send triggers notification fan-out via existing backend (no frontend change).
- Resolved comments: toggled to a lower-opacity state, not hidden, with a "resolve/unresolve" inline action.
- Comment dot on node: amber circle top-right; shows count when >0; clicking the dot selects the span and switches the sidebar to the Thread tab.

## Full-screen mode

- Activation: `F` key, toolbar button, or `?fs=1` in URL.
- Layout when active:
  - Top bar of the app shell stays.
  - Trajectory header shrinks to a slim strip (one-line summary: agent · status · duration · tag · "exit full-screen" chip).
  - Tree pane collapses to a 24px rail on the left. Click the rail → tree appears as a floating overlay panel that can be dismissed.
  - Graph fills the remaining viewport.
  - Floating inspector appears bottom-right of the graph when a span is selected.
  - Sidebar remains on the right unless the user has collapsed it.
- Exit: `Esc`, toolbar button, or clearing `?fs=1`.
- URL persistence: pushState when toggling so back/forward works.

## Deep linking

- `/t/<trajectory_id>` — default view, split layout.
- `/t/<trajectory_id>?fs=1` — full-screen mode.
- `/t/<trajectory_id>?span=<span_id>` — trajectory opens with that span selected.
- `/t/<trajectory_id>?fs=1&span=<span_id>&tab=thread` — full-screen, span selected, sidebar on Thread tab. (Shareable deep link — matches the collab use case of "look at this comment I left.")

## Error handling

- Missing/malformed attributes → fall back to the raw JSON inside the expanded body; no crash.
- Empty `spans[]` → graph renders the existing `"No spans to graph."` message; toolbar disabled.
- Comment endpoint 401 / 404 → Thread tab shows an inline error with a retry button; graph stays usable.
- localStorage unavailable (e.g. private browsing) → sidebar falls back to default width/open; no exception.
- User navigates away while a comment compose is pending → send completes in background; error surfaces as a notification if the page is still open.

## Testing

- **Playwright** (`web/tests/graph-redesign.spec.ts`):
  1. Open a trajectory → graph renders with labelled edges visible.
  2. Click a node → inline body visible; click again → collapsed.
  3. Click toolbar "expand all" → every node's body visible.
  4. Press `F` → full-screen layout; floating inspector appears on node select.
  5. Resize sidebar → reload → width persists.
  6. Open Thread tab, post a comment → appears in the list without a full reload.
- **Unit** (`web/tests/lib/graph-edges.test.ts`): given a canned span list, expect the correct `Edge[]` labels and targets.
- **Unit** (`web/tests/hooks/expand-state.test.ts`): global expand-all overrides per-span compact; per-span override wins over global compact; toggles compose correctly.
- **Visual** (manual): full-screen mode looks right in Chrome + Safari at 1280, 1920 widths.

## Rollout

- Behind no flag; land as a single shipped PR.
- Dogfood period: Andrew uses the new graph on his own agent runs. Collect impressions before any further tuning.
- If something regresses, revert is clean (one PR, additive files, touching only graph + sidebar + trajectory-view layer).

## Open questions deferred to implementation

- Exact truncation ellipsis character (`…` vs "show more (+N chars)") — implementer's call, either is fine.
- Whether the floating inspector should dismiss on second click of the same node, or stay until explicitly closed — implementer's call; lean toward staying.
- Whether to render the trajectory-level thread dot on the trajectory header or only inside the sidebar — implementer's call; lean toward header dot for parity with node dots.
- Tree pane overlay: width + how it dismisses (click outside vs explicit close) — implementer's call.

## References

- v2b collab primitives plan: `docs/superpowers/plans/2026-04-17-v2b-collab-primitives.md`
- Existing graph: `web/components/trajectory-graph.tsx`
- Existing sidebar: `web/components/node-detail-panel.tsx`
- Visual companion artifacts: `.superpowers/brainstorm/23948-1776614625/content/`
