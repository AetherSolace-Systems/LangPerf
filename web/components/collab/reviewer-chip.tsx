"use client";

import { useState } from "react";

import { assignReviewer } from "@/lib/collab";

type Member = { id: string; display_name: string };

export function ReviewerChip({
  trajectoryId,
  current,
  members,
}: {
  trajectoryId: string;
  current: Member | null;
  members: Member[];
}) {
  const [open, setOpen] = useState(false);
  const [assigned, setAssigned] = useState<Member | null>(current);

  async function pick(m: Member | null) {
    setAssigned(m);
    await assignReviewer(trajectoryId, m?.id ?? null);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((x) => !x)}
        className="rounded-full bg-warm-fog/10 px-2 py-1 text-xs text-warm-fog hover:bg-warm-fog/20"
      >
        {assigned ? `@${assigned.display_name}` : "Assign"}
      </button>
      {open && (
        <div className="absolute z-40 mt-1 w-44 rounded-lg bg-carbon p-1 ring-1 ring-warm-fog/20">
          <button onClick={() => pick(null)} className="block w-full px-2 py-1 text-left text-xs hover:bg-warm-fog/10">
            Unassign
          </button>
          {members.map((m) => (
            <button
              key={m.id}
              onClick={() => pick(m)}
              className="block w-full px-2 py-1 text-left text-xs text-warm-fog hover:bg-warm-fog/10"
            >
              {m.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
