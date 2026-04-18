"use client";

import { useEffect, useState } from "react";

import { type FailureMode, listFailureModes, tagFailureMode, untagFailureMode } from "@/lib/collab";

export function FailureModePicker({
  trajectoryId,
  current,
}: {
  trajectoryId: string;
  current: FailureMode[];
}) {
  const [all, setAll] = useState<FailureMode[]>([]);
  const [tagged, setTagged] = useState<FailureMode[]>(current);

  useEffect(() => {
    listFailureModes().then(setAll);
  }, []);

  async function toggle(m: FailureMode) {
    const isTagged = tagged.some((t) => t.id === m.id);
    if (isTagged) {
      await untagFailureMode(trajectoryId, m.id);
      setTagged((prev) => prev.filter((t) => t.id !== m.id));
    } else {
      await tagFailureMode(trajectoryId, m.id);
      setTagged((prev) => [...prev, m]);
    }
  }

  return (
    <div className="flex flex-wrap gap-1">
      {all.map((m) => {
        const active = tagged.some((t) => t.id === m.id);
        return (
          <button
            key={m.id}
            onClick={() => toggle(m)}
            className={`rounded-full px-2 py-0.5 text-xs ring-1 ${
              active ? "bg-warn/20 text-warn ring-warn" : "bg-warm-fog/5 text-warm-fog/70 ring-warm-fog/20"
            }`}
          >
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
