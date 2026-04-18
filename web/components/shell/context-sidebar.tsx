import type { ReactNode } from "react";

export type ContextSidebarProps = {
  children: ReactNode;
  className?: string;
};

/**
 * 220px fixed-width sidebar that lives between the icon rail and the main
 * content. Pages own their sidebar content — this component just provides
 * the consistent frame (width, border, padding, scrollbar).
 */
export function ContextSidebar({ children, className = "" }: ContextSidebarProps) {
  return (
    <aside
      className={`w-[220px] border-r border-[color:var(--border)] bg-[color:var(--background)] px-[10px] py-[12px] overflow-y-auto ${className}`}
    >
      {children}
    </aside>
  );
}

/**
 * Helper components so pages don't re-invent the header/item styling.
 */
export function CtxHeader({
  children,
  action,
}: {
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between px-[4px] pt-[6px] pb-[4px] font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
      <span>{children}</span>
      {action ? <span className="text-aether-teal">{action}</span> : null}
    </div>
  );
}

export function CtxItem({
  children,
  active = false,
  sub,
}: {
  children: ReactNode;
  active?: boolean;
  sub?: ReactNode;
}) {
  return (
    <div
      className={`flex items-center gap-2 px-[6px] py-[5px] rounded-[2px] text-[12px] my-[1px] ${
        active ? "bg-[color:rgba(107,186,177,0.07)] text-warm-fog" : "text-warm-fog"
      }`}
    >
      <span className="flex-1 truncate">{children}</span>
      {sub ? <span className="font-mono text-[10px] text-patina">{sub}</span> : null}
    </div>
  );
}
