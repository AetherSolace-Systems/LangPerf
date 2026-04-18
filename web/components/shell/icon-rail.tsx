"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { RAIL_ITEMS, type RailItem } from "@/components/shell/nav-config";

function isActive(pathname: string, item: RailItem): boolean {
  if (item.v2) return false;
  if (item.href === "/") return pathname === "/";
  if (item.exact) return pathname === item.href;
  return pathname === item.href || pathname.startsWith(`${item.href}/`);
}

function RailCell({ item, active }: { item: RailItem; active: boolean }) {
  const base =
    "flex flex-col items-center gap-[2px] px-[2px] py-[8px] text-[9px] uppercase tracking-[0.08em] border-l-2 border-transparent";
  const state = item.v2
    ? "text-patina opacity-55 cursor-not-allowed"
    : active
      ? "text-aether-teal border-l-aether-teal bg-[color:rgba(107,186,177,0.04)]"
      : "text-patina hover:text-warm-fog";
  const body = (
    <>
      <span className="font-mono text-[12px]">{item.glyph}</span>
      <span>{item.label}</span>
    </>
  );
  if (item.v2) {
    return (
      <div className={`${base} ${state}`} title="v2 · coming soon" aria-disabled="true">
        {body}
      </div>
    );
  }
  return (
    <Link href={item.href} className={`${base} ${state}`}>
      {body}
    </Link>
  );
}

export function IconRail() {
  const pathname = usePathname() ?? "/";
  const primary = RAIL_ITEMS.filter((i) => i.group === "primary");
  const later = RAIL_ITEMS.filter((i) => i.group === "later");
  const footer = RAIL_ITEMS.filter((i) => i.group === "footer");

  return (
    <nav className="w-[56px] border-r border-[color:var(--border)] bg-[color:var(--surface-2)] flex flex-col py-[8px] gap-[2px]">
      {primary.map((i) => (
        <RailCell key={i.id} item={i} active={isActive(pathname, i)} />
      ))}
      <div className="h-px bg-[color:var(--border)] mx-[8px] my-[6px]" />
      {later.map((i) => (
        <RailCell key={i.id} item={i} active={false} />
      ))}
      <div className="flex-1" />
      <div className="h-px bg-[color:var(--border)] mx-[8px] my-[6px]" />
      {footer.map((i) => (
        <RailCell key={i.id} item={i} active={isActive(pathname, i)} />
      ))}
    </nav>
  );
}
