"use client";

import { useState } from "react";
import type { TrajectoryDetail } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { useSelection } from "@/components/selection-context";
import { ResizableSidebar } from "@/components/sidebar/resizable-sidebar";
import {
  SidebarTabs,
  TabPane,
  type TabId,
} from "@/components/sidebar/sidebar-tabs";
import { DetailTab } from "@/components/sidebar/detail-tab";
import { NotesTab } from "@/components/sidebar/notes-tab";
import { ThreadTab } from "@/components/sidebar/thread-tab";

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
