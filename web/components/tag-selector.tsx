"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { patchTrajectory } from "@/lib/client-api";

const TAGS = ["good", "bad", "interesting", "todo"] as const;
type Tag = (typeof TAGS)[number] | null;

const tagStyles: Record<string, string> = {
  good: "bg-emerald-500/20 text-emerald-200 border-emerald-500/50",
  bad: "bg-rose-500/20 text-rose-200 border-rose-500/50",
  interesting: "bg-sky-500/20 text-sky-200 border-sky-500/50",
  todo: "bg-amber-500/20 text-amber-200 border-amber-500/50",
};

export function TagSelector({
  trajectoryId,
  value,
}: {
  trajectoryId: string;
  value: string | null;
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();

  const apply = async (tag: Tag) => {
    try {
      if (tag === null) {
        await patchTrajectory(trajectoryId, { clear_tag: true });
      } else {
        await patchTrajectory(trajectoryId, { status_tag: tag });
      }
      startTransition(() => router.refresh());
    } catch (err) {
      alert(`failed to tag: ${err}`);
    }
  };

  return (
    <div className="inline-flex items-center gap-1 text-[10px] font-mono uppercase tracking-wider">
      {TAGS.map((t) => {
        const active = value === t;
        return (
          <button
            key={t}
            type="button"
            onClick={() => apply(active ? null : t)}
            disabled={pending}
            className={`border rounded px-2 py-0.5 transition-colors ${
              active
                ? tagStyles[t]
                : "bg-transparent text-[var(--muted)] border-[var(--border)] hover:border-[var(--foreground)]/30 hover:text-[var(--foreground)]/80"
            } ${pending ? "opacity-50" : ""}`}
          >
            {t}
          </button>
        );
      })}
    </div>
  );
}
