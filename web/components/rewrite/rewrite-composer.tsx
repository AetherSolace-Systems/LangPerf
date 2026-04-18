"use client";

import { useState } from "react";

import { createRewrite, type ProposedStep, type Rewrite } from "@/lib/rewrites";
import { RewriteStepEditor } from "./rewrite-step-editor";

export function RewriteComposer({
  trajectoryId,
  branchSpanId,
  onCreated,
  onCancel,
}: {
  trajectoryId: string;
  branchSpanId: string;
  onCreated: (r: Rewrite) => void;
  onCancel: () => void;
}) {
  const [rationale, setRationale] = useState("");
  const [steps, setSteps] = useState<ProposedStep[]>([
    { kind: "tool_call", tool_name: "", arguments: {} },
  ]);
  const [pending, setPending] = useState(false);

  async function save(status: "draft" | "submitted") {
    setPending(true);
    try {
      const r = await createRewrite(trajectoryId, {
        branch_span_id: branchSpanId,
        rationale,
        proposed_steps: steps,
        status,
      });
      onCreated(r);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-xl bg-warm-fog/5 p-4 ring-1 ring-aether-teal/30">
      <header>
        <p className="text-xs uppercase tracking-wide text-aether-teal">Propose rewrite</p>
        <p className="text-[0.65rem] text-warm-fog/50">Branch point: {branchSpanId}</p>
      </header>
      <textarea
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        placeholder="Why was the agent wrong here?"
        rows={3}
        className="w-full resize-none rounded-lg bg-carbon px-3 py-2 text-sm text-warm-fog"
      />
      <div className="space-y-2">
        {steps.map((s, i) => (
          <RewriteStepEditor
            key={i}
            step={s}
            onChange={(next) => setSteps((prev) => prev.map((x, j) => (j === i ? next : x)))}
            onRemove={() => setSteps((prev) => prev.filter((_, j) => j !== i))}
          />
        ))}
        <button
          onClick={() => setSteps((prev) => [...prev, { kind: "tool_call", tool_name: "", arguments: {} }])}
          className="rounded bg-warm-fog/10 px-3 py-1 text-xs text-warm-fog"
        >
          + Step
        </button>
      </div>
      <div className="flex justify-end gap-2">
        <button onClick={onCancel} className="rounded px-3 py-1 text-xs text-warm-fog/60">Cancel</button>
        <button
          onClick={() => save("draft")}
          disabled={pending}
          className="rounded bg-warm-fog/10 px-3 py-1 text-xs text-warm-fog disabled:opacity-50"
        >
          Save draft
        </button>
        <button
          onClick={() => save("submitted")}
          disabled={pending}
          className="rounded bg-aether-teal px-3 py-1 text-xs font-semibold text-carbon disabled:opacity-50"
        >
          {pending ? "Saving…" : "Submit"}
        </button>
      </div>
    </div>
  );
}
