"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import type { TimeWindow } from "@/lib/api";

const OPTIONS: TimeWindow[] = ["24h", "7d", "30d"];

export function TimeRangePicker({ current }: { current: TimeWindow }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const set = (w: TimeWindow) => {
    const next = new URLSearchParams(params.toString());
    next.set("window", w);
    router.push(`${pathname}?${next.toString()}`);
  };

  return (
    <span className="inline-flex border border-[color:var(--border-strong)] rounded-[3px] overflow-hidden">
      {OPTIONS.map((w) => {
        const on = w === current;
        return (
          <button
            key={w}
            type="button"
            onClick={() => set(w)}
            className={`px-[10px] py-[4px] text-[10px] font-mono uppercase tracking-[0.08em] border-r last:border-r-0 border-[color:var(--border)] ${
              on ? "bg-[color:rgba(107,186,177,0.08)] text-aether-teal" : "text-patina hover:text-warm-fog"
            }`}
          >
            {w}
          </button>
        );
      })}
    </span>
  );
}
