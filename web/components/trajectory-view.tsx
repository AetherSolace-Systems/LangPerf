"use client";

import { useCallback, useState } from "react";
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

type LowerView = "graph" | "timeline";

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
  const [lowerView, setLowerView] = useState<LowerView>("timeline");
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
          <SectionHeader label="Tree" />
          <div className="flex-shrink-0 overflow-y-auto max-h-[30%] border-b border-[color:var(--border)]">
            <TrajectoryTree spans={trajectory.spans} />
          </div>
          <div className="flex-1 min-h-0 flex flex-col">
            <SectionHeader
              label={lowerView === "graph" ? "Graph" : "Timeline"}
              right={
                <div className="flex gap-1">
                  <ToggleButton
                    active={lowerView === "timeline"}
                    onClick={() => setLowerView("timeline")}
                  >
                    timeline
                  </ToggleButton>
                  <ToggleButton
                    active={lowerView === "graph"}
                    onClick={() => setLowerView("graph")}
                  >
                    graph
                  </ToggleButton>
                </div>
              }
            />
            <div className="flex-1 min-h-0">
              {lowerView === "graph" ? (
                <TrajectoryGraph
                  spans={trajectory.spans}
                  commentCounts={commentCounts}
                />
              ) : (
                <TrajectoryTimeline spans={trajectory.spans} />
              )}
            </div>
          </div>
        </div>
        <NodeDetailPanel trajectory={trajectory} />
      </div>
    </div>
  );
}

function Dot() {
  return <span className="text-xs text-patina">·</span>;
}

function SectionHeader({
  label,
  right,
}: {
  label: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-patina bg-carbon/40 flex-shrink-0 border-b border-[color:var(--border)] flex items-center justify-between">
      <span>{label}</span>
      {right}
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2 py-0.5 rounded border text-[10px] uppercase tracking-wider transition-colors ${
        active
          ? "border-aether-teal text-aether-teal bg-aether-teal/10"
          : "border-[color:var(--border)] text-patina hover:text-warm-fog hover:border-patina"
      }`}
    >
      {children}
    </button>
  );
}
