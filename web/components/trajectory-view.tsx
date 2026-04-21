"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import type { TrajectoryDetail } from "@/lib/api";
import { fmtDuration } from "@/lib/format";
import { ClientTime } from "@/components/client-time";
import { NodeDetailPanel } from "@/components/node-detail-panel";
import { NotesEditor } from "@/components/notes-editor";
import { FullscreenProvider } from "@/components/graph/fullscreen-context";
import { useFullscreen } from "@/components/graph/fullscreen-context";
import { useGraphKeyboard } from "@/components/graph/use-graph-keyboard";
import { useGraphUrlSync } from "@/components/graph/use-graph-url-sync";
import { SelectionProvider } from "@/components/selection-context";
import { TagSelector } from "@/components/tag-selector";
import { TrajectoryGraph } from "@/components/trajectory-graph";
import { useCommentCounts } from "@/lib/comment-counts";
import { TrajectoryTimeline } from "@/components/trajectory-timeline";
import { TrajectoryTree } from "@/components/trajectory-tree";

type PaneKey = "tree" | "timeline" | "graph";

// Collapsed = not showing; expanded panes share the remaining vertical
// space via flex-1. Persisted per-pane under one JSON blob so the user's
// preferred combo survives reloads and navigations.
const LAYOUT_STORAGE_KEY = "langperf.trajectory.collapsed";
type CollapsedState = Record<PaneKey, boolean>;
const DEFAULT_COLLAPSED: CollapsedState = {
  tree: false,
  timeline: false,
  graph: false,
};

function loadCollapsed(): CollapsedState {
  if (typeof window === "undefined") return DEFAULT_COLLAPSED;
  try {
    const raw = window.localStorage.getItem(LAYOUT_STORAGE_KEY);
    if (!raw) return DEFAULT_COLLAPSED;
    const parsed = JSON.parse(raw);
    return {
      tree: Boolean(parsed?.tree),
      timeline: Boolean(parsed?.timeline),
      graph: Boolean(parsed?.graph),
    };
  } catch {
    return DEFAULT_COLLAPSED;
  }
}

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
  const [notesOpen, setNotesOpen] = useState<boolean>(!!trajectory.notes);
  const [collapsed, setCollapsed] = useState<CollapsedState>(DEFAULT_COLLAPSED);
  // Hydrate from localStorage after mount to avoid SSR/CSR flashes.
  useEffect(() => setCollapsed(loadCollapsed()), []);
  const toggleCollapsed = useCallback((pane: PaneKey) => {
    setCollapsed((prev) => {
      const next = { ...prev, [pane]: !prev[pane] };
      try {
        window.localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Private mode or quota — no-op; collapse still applies this session.
      }
      return next;
    });
  }, []);
  const commentCounts = useCommentCounts(trajectory);
  const { fsOpen, toggleFs, toggleExpandAll, collapseAll, setFs } = useFullscreen();

  const exitFullscreen = useCallback((): boolean => {
    if (!fsOpen) return false;
    setFs(false);
    return true;
  }, [fsOpen, setFs]);

  useGraphKeyboard({
    toggleFullscreen: toggleFs,
    exitFullscreen,
    expandAll: toggleExpandAll,
    collapseAll,
  });
  useGraphUrlSync(fsOpen, setFs);

  if (fsOpen) {
    return (
      <div
        data-fs="1"
        className="fixed inset-0 z-50 flex flex-col bg-[color:var(--background)]"
      >
        <div className="flex items-center gap-2 px-3 py-2 border-b border-[color:var(--border)] flex-shrink-0">
          <span className="font-mono text-[10px] text-patina uppercase tracking-wider">run</span>
          <span className="text-xs text-warm-fog/90 truncate">
            {trajectory.name ?? "(unnamed)"}
          </span>
          <span className="text-xs font-mono text-patina">
            {trajectory.id.slice(0, 8)}…
          </span>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => toggleFs()}
            className="text-[10px] uppercase tracking-wider text-patina hover:text-warm-fog border border-[color:var(--border)] rounded px-2 py-0.5"
            title="Exit full-screen (Esc)"
          >
            exit full-screen
          </button>
        </div>
        <div className="flex flex-1 overflow-hidden">
          <div className="flex-1 min-w-0">
            <TrajectoryGraph
              spans={trajectory.spans}
              commentCounts={commentCounts}
            />
          </div>
          <NodeDetailPanel trajectory={trajectory} />
        </div>
      </div>
    );
  }

  return (
    <div data-fs="0" className="h-screen flex flex-col">
      <header className="border-b border-[color:var(--border)] px-6 py-3 flex-shrink-0">
        <Link href="/" className="text-xs text-patina hover:text-warm-fog">
          ← all trajectories
        </Link>
        <div className="mt-1 flex items-baseline gap-3 flex-wrap">
          <h1 className="text-base font-semibold tracking-tight">
            {trajectory.name ?? (
              <em className="text-patina font-normal">(unnamed)</em>
            )}
          </h1>
          <span className="text-xs font-mono text-patina">
            {trajectory.id.slice(0, 8)}…
          </span>
          <Dot />
          <span className="text-xs text-patina">
            {trajectory.service_name}
            {trajectory.environment ? ` · ${trajectory.environment}` : ""}
          </span>
          <Dot />
          <span className="text-xs text-patina tabular-nums">
            {trajectory.step_count} step{trajectory.step_count === 1 ? "" : "s"}
          </span>
          <Dot />
          <span className="text-xs text-patina tabular-nums">
            {trajectory.token_count.toLocaleString()}t
          </span>
          <Dot />
          <span className="text-xs text-patina tabular-nums">
            {fmtDuration(trajectory.duration_ms)}
          </span>
          <Dot />
          <span className="text-xs text-patina">
            <ClientTime iso={trajectory.started_at} />
          </span>
        </div>

        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <TagSelector
            trajectoryId={trajectory.id}
            value={trajectory.status_tag}
          />
          <button
            type="button"
            onClick={() => setNotesOpen((v) => !v)}
            className="text-[10px] uppercase tracking-wider text-patina hover:text-warm-fog border border-[color:var(--border)] rounded px-2 py-0.5"
          >
            {notesOpen ? "hide notes" : trajectory.notes ? "notes" : "+ notes"}
          </button>
        </div>

        {notesOpen ? (
          <div className="mt-3 max-w-2xl">
            <NotesEditor
              target={{ kind: "trajectory", id: trajectory.id }}
              value={trajectory.notes}
              placeholder="Notes on this trajectory (markdown allowed)…"
            />
          </div>
        ) : null}
      </header>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 min-w-0 flex flex-col border-r border-[color:var(--border)]">
          <Pane
            label="Tree"
            collapsed={collapsed.tree}
            onToggle={() => toggleCollapsed("tree")}
          >
            <div className="h-full overflow-y-auto">
              <TrajectoryTree spans={trajectory.spans} />
            </div>
          </Pane>
          <Pane
            label="Timeline"
            collapsed={collapsed.timeline}
            onToggle={() => toggleCollapsed("timeline")}
          >
            <TrajectoryTimeline spans={trajectory.spans} />
          </Pane>
          <Pane
            label="Graph"
            collapsed={collapsed.graph}
            onToggle={() => toggleCollapsed("graph")}
          >
            <TrajectoryGraph
              spans={trajectory.spans}
              commentCounts={commentCounts}
            />
          </Pane>
        </div>
        <NodeDetailPanel trajectory={trajectory} />
      </div>
    </div>
  );
}

/**
 * Stacked collapsible section. Expanded panes share remaining vertical
 * space (flex-1 + min-h-0 so children can shrink); collapsed panes
 * shrink to just their header row. The caret rotates 0° → 90° on
 * collapse for a cheap click-target affordance.
 */
function Pane({
  label,
  collapsed,
  onToggle,
  children,
}: {
  label: string;
  collapsed: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section
      className={
        "flex flex-col border-b border-[color:var(--border)] last:border-b-0 " +
        (collapsed ? "flex-shrink-0" : "flex-1 min-h-0")
      }
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={!collapsed}
        aria-controls={`pane-${label.toLowerCase()}-body`}
        className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-patina bg-carbon/40 flex-shrink-0 flex items-center gap-2 hover:text-warm-fog hover:bg-carbon/60 transition-colors text-left"
      >
        <span
          aria-hidden
          className="inline-block transition-transform duration-150"
          style={{ transform: collapsed ? "rotate(0deg)" : "rotate(90deg)" }}
        >
          ›
        </span>
        <span>{label}</span>
      </button>
      {collapsed ? null : (
        <div id={`pane-${label.toLowerCase()}-body`} className="flex-1 min-h-0">
          {children}
        </div>
      )}
    </section>
  );
}

function Dot() {
  return <span className="text-xs text-patina">·</span>;
}
