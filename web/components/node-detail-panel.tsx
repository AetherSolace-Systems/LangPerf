"use client";

import { useState } from "react";
import type { Span, TrajectoryDetail } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { GenericSpanView } from "@/components/views/generic-span-view";
import { LlmSpanView } from "@/components/views/llm-span-view";
import { ToolSpanView } from "@/components/views/tool-span-view";
import { NotesEditor } from "@/components/notes-editor";
import { useSelection } from "@/components/selection-context";
import { ResizableSidebar } from "@/components/sidebar/resizable-sidebar";
import {
  SidebarTabs,
  TabPane,
  type TabId,
} from "@/components/sidebar/sidebar-tabs";
import { CommentThread } from "@/components/collab/comment-thread";

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
  if (!trajectory) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">Loading trajectory…</div>
    );
  }
  if (!span) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Select a node to join the conversation.
      </div>
    );
  }
  return (
    <div className="p-5">
      <CommentThread trajectoryId={trajectory.id} spanId={span.span_id} />
    </div>
  );
}
