"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { patchNode, patchTrajectory } from "@/lib/client-api";

type Target =
  | { kind: "trajectory"; id: string }
  | { kind: "node"; id: string };

export function NotesEditor({
  target,
  value,
  placeholder = "Add notes…",
  compact = false,
}: {
  target: Target;
  value: string | null;
  placeholder?: string;
  compact?: boolean;
}) {
  const router = useRouter();
  const [notes, setNotes] = useState(value ?? "");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [, startTransition] = useTransition();

  const save = async () => {
    if (saving) return;
    setSaving(true);
    try {
      const patch =
        notes.trim() === ""
          ? { clear_notes: true }
          : { notes };
      if (target.kind === "trajectory") {
        await patchTrajectory(target.id, patch);
      } else {
        await patchNode(target.id, patch);
      }
      setDirty(false);
      startTransition(() => router.refresh());
    } catch (err) {
      alert(`failed to save notes: ${err}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className={compact ? "space-y-1" : "space-y-2"}>
      <textarea
        value={notes}
        onChange={(e) => {
          setNotes(e.target.value);
          setDirty(e.target.value !== (value ?? ""));
        }}
        onBlur={() => {
          if (dirty) save();
        }}
        placeholder={placeholder}
        rows={compact ? 2 : 3}
        className="w-full text-xs bg-black/30 border border-[var(--border)] rounded p-2 font-mono text-[var(--foreground)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)]/60 resize-y"
      />
      <div className="flex items-center gap-2 text-[10px] text-[var(--muted)]">
        <span>
          {saving ? "saving…" : dirty ? "unsaved — blur to save" : "saved"}
        </span>
        {dirty ? (
          <button
            type="button"
            onClick={save}
            className="border border-[var(--border)] rounded px-2 py-0.5 hover:border-[var(--accent)]/60 hover:text-[var(--foreground)]"
          >
            save now
          </button>
        ) : null}
      </div>
    </div>
  );
}
