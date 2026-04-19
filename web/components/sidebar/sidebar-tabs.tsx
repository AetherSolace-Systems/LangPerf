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
    <div role="tablist" className="flex border-b border-[color:var(--border)]">
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
