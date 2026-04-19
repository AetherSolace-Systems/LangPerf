"use client";

import type { Span, TrajectoryDetail } from "@/lib/api";
import { kindOf } from "@/lib/span-fields";
import { NotesEditor } from "@/components/notes-editor";

export function NotesTab({
  span,
  trajectory,
  onSelect,
}: {
  span: Span | null;
  trajectory?: TrajectoryDetail;
  onSelect: (s: Span) => void;
}) {
  if (span) {
    return (
      <div className="p-5">
        <NotesEditor
          key={span.span_id}
          target={{ kind: "node", id: span.span_id }}
          value={span.notes}
          placeholder="Notes on this node…"
          compact
        />
      </div>
    );
  }
  if (!trajectory) {
    return (
      <div className="p-6 text-sm text-[color:var(--muted)]">
        Select a node to add notes.
      </div>
    );
  }
  const annotated = trajectory.spans.filter(
    (s) => (s.notes ?? "").trim() !== "",
  );
  const trajectoryHasNote = (trajectory.notes ?? "").trim() !== "";
  return (
    <div className="p-5 space-y-4">
      <NotesEditor
        target={{ kind: "trajectory", id: trajectory.id }}
        value={trajectory.notes}
        placeholder="Notes on this run…"
        compact
      />
      {annotated.length === 0 && !trajectoryHasNote ? (
        <p className="text-xs text-[color:var(--muted)] italic">
          Per-node notes show up here once you add them.
        </p>
      ) : (
        annotated.map((s) => (
          <button
            key={s.span_id}
            type="button"
            onClick={() => onSelect(s)}
            className="w-full text-left rounded border border-[color:var(--border)] bg-[color:var(--surface-2)] p-3 hover:border-aether-teal/60"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] uppercase tracking-wider text-[color:var(--muted)]">
                {kindOf(s).toUpperCase()}
              </span>
              <span className="text-xs font-medium truncate">{s.name}</span>
            </div>
            <div className="text-xs whitespace-pre-wrap">{s.notes}</div>
          </button>
        ))
      )}
    </div>
  );
}
