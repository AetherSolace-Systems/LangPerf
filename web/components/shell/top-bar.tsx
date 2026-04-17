import type { ReactNode } from "react";
import Link from "next/link";
import { Chip } from "@/components/ui/chip";

export type TopBarProps = {
  /** Breadcrumb content rendered next to the logo. Can be a single label or a chain of <Link>s. */
  breadcrumb?: ReactNode;
  /** Right-side slot — env chip, ingest status, etc. */
  right?: ReactNode;
  /** When true, hide the search input (e.g. on narrow layouts). */
  hideSearch?: boolean;
};

export function TopBar({ breadcrumb, right, hideSearch = false }: TopBarProps) {
  return (
    <header className="flex items-center gap-3 px-4 py-[9px] border-b border-[color:var(--border)] bg-[color:var(--surface)]">
      <Link href="/" className="font-semibold text-[13px] tracking-[-0.01em] select-none">
        <span className="text-aether-teal">lang</span>
        <span className="text-peach-neon">perf</span>
      </Link>
      {breadcrumb ? (
        <div className="text-[12px] text-patina flex items-center gap-2">{breadcrumb}</div>
      ) : null}
      <div className="flex-1" />
      {!hideSearch ? (
        <div className="max-w-[260px] flex-1">
          <input
            type="text"
            placeholder="⌘k · fuzzy · my_agent.*.*"
            className="w-full bg-[color:var(--background)] border border-[color:var(--border)] rounded-[3px] px-[10px] py-[5px] text-[11px] font-mono text-warm-fog placeholder:text-patina focus:outline-none focus:border-[color:var(--border-strong)]"
            disabled
            aria-disabled="true"
            title="Global search lands in a follow-up plan"
          />
        </div>
      ) : null}
      {right ?? <Chip>env: all</Chip>}
    </header>
  );
}
