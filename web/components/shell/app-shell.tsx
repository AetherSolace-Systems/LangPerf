import type { ReactNode } from "react";
import { IconRail } from "@/components/shell/icon-rail";
import { TopBar, type TopBarProps } from "@/components/shell/top-bar";

export type AppShellProps = {
  /** Top-bar props forwarded verbatim. */
  topBar?: TopBarProps;
  /** Optional context sidebar. Pass a <ContextSidebar>…</ContextSidebar> node, or omit for a two-zone layout. */
  contextSidebar?: ReactNode;
  /** Main content. */
  children: ReactNode;
};

export function AppShell({ topBar, contextSidebar, children }: AppShellProps) {
  return (
    <div className="min-h-screen flex flex-col bg-[color:var(--background)] text-[color:var(--foreground)]">
      <TopBar {...(topBar ?? {})} />
      <div className="flex flex-1 min-h-0">
        <IconRail />
        {contextSidebar}
        <main className="flex-1 min-w-0 overflow-auto p-[14px]">{children}</main>
      </div>
    </div>
  );
}
