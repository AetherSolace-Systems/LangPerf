import type { ReactNode } from "react";
import { headers } from "next/headers";
import { IconRail } from "@/components/shell/icon-rail";
import { TopBar, type TopBarProps } from "@/components/shell/top-bar";
import { UserMenu } from "@/components/shell/user-menu";
import { fetchMe } from "@/lib/auth";

export type AppShellProps = {
  /** Top-bar props forwarded verbatim. */
  topBar?: TopBarProps;
  /** Optional context sidebar. Pass a <ContextSidebar>…</ContextSidebar> node, or omit for a two-zone layout. */
  contextSidebar?: ReactNode;
  /** Main content. */
  children: ReactNode;
};

export async function AppShell({ topBar, contextSidebar, children }: AppShellProps) {
  let me = null;
  try {
    const cookie = headers().get("cookie") ?? undefined;
    me = await fetchMe(cookie);
  } catch {
    // fetchMe failure (e.g. API down) should not crash the shell
  }

  const rightContent = (
    <div className="flex items-center gap-2">
      {topBar?.right}
      <UserMenu user={me} />
    </div>
  );

  return (
    <div className="min-h-screen flex flex-col bg-[color:var(--background)] text-[color:var(--foreground)]">
      <TopBar {...(topBar ?? {})} right={rightContent} />
      <div className="flex flex-1 min-h-0">
        <IconRail />
        {contextSidebar}
        <main className="flex-1 min-w-0 overflow-auto p-[14px]">{children}</main>
      </div>
    </div>
  );
}
