"use client";

import { apiBase } from "@/lib/api";

export function ExportBar({
  agentName,
  window,
}: {
  agentName: string;
  window: "24h" | "7d" | "30d";
}) {
  const base = apiBase();
  const agent = encodeURIComponent(agentName);
  return (
    <div className="flex items-center gap-[6px]">
      <a
        href={`${base}/api/agents/${agent}/profile.md?window=${window}`}
        download
        className="font-mono text-[10px] uppercase tracking-wider border border-peach-neon text-peach-neon rounded px-[8px] py-[3px] hover:bg-peach-neon/10"
      >
        ↓ profile.md
      </a>
      <a
        href={`${base}/api/agents/${agent}/failures.csv?window=${window}`}
        download
        className="font-mono text-[10px] uppercase tracking-wider border border-peach-neon text-peach-neon rounded px-[8px] py-[3px] hover:bg-peach-neon/10"
      >
        ↓ failures.csv
      </a>
    </div>
  );
}
