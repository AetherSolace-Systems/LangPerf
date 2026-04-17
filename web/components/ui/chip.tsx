import type { ReactNode } from "react";

export type ChipVariant = "default" | "primary" | "accent" | "warn" | "on";

export function Chip({
  children,
  variant = "default",
  className = "",
}: {
  children: ReactNode;
  variant?: ChipVariant;
  className?: string;
}) {
  const variantCls: Record<ChipVariant, string> = {
    default:
      "text-patina border-[color:var(--border-strong)]",
    primary:
      "text-aether-teal border-[color:rgba(107,186,177,0.45)]",
    accent:
      "text-peach-neon border-[color:rgba(232,168,124,0.45)]",
    warn:
      "text-warn border-[color:rgba(217,138,106,0.4)]",
    on:
      "bg-[color:rgba(107,186,177,0.1)] text-aether-teal border-[color:rgba(107,186,177,0.45)]",
  };
  return (
    <span
      className={`inline-flex items-center px-[7px] py-[2px] rounded-[2px] text-[10px] uppercase tracking-[0.08em] font-mono whitespace-nowrap border ${variantCls[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
