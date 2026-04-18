"use client";

import { useRouter, useSearchParams } from "next/navigation";

const HEURISTICS = [
  ["tool_error", "Tool errors"],
  ["latency_outlier", "Latency outliers"],
  ["apology_phrase", "Apologies"],
  ["loop", "Loops"],
  ["low_confidence", "Low confidence"],
] as const;

export function FilterBar() {
  const router = useRouter();
  const params = useSearchParams();
  const active = new Set(params.getAll("heuristic"));

  function toggle(h: string) {
    const next = new Set(active);
    if (next.has(h)) next.delete(h);
    else next.add(h);
    const qs = new URLSearchParams();
    next.forEach((x) => qs.append("heuristic", x));
    router.push(`/queue?${qs.toString()}`);
  }

  return (
    <div className="flex flex-wrap gap-2">
      {HEURISTICS.map(([slug, label]) => (
        <button
          key={slug}
          onClick={() => toggle(slug)}
          className={`rounded-full px-3 py-1 text-xs ring-1 ${
            active.has(slug)
              ? "bg-aether-teal/20 text-aether-teal ring-aether-teal"
              : "bg-warm-fog/5 text-warm-fog/70 ring-warm-fog/20"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
