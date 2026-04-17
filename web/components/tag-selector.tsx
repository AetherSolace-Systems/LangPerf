"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { tagSwatch } from "@/lib/colors";
import { patchTrajectory } from "@/lib/client-api";

const TAGS = ["good", "bad", "interesting", "todo"] as const;
type Tag = (typeof TAGS)[number] | null;

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
        const swatch = tagSwatch(t);
        return (
          <button
            key={t}
            type="button"
            onClick={() => apply(active ? null : t)}
            disabled={pending}
            className="border rounded px-2 py-0.5 transition-colors"
            style={{
              color: active ? swatch.fg : "var(--muted)",
              background: active ? swatch.bg : "transparent",
              borderColor: active ? swatch.border : "var(--border)",
              opacity: pending ? 0.5 : 1,
            }}
          >
            {t}
          </button>
        );
      })}
    </div>
  );
}
