"use client";

import type { ProposedStep } from "@/lib/rewrites";

export function RewriteStepEditor({
  step,
  onChange,
  onRemove,
}: {
  step: ProposedStep;
  onChange: (next: ProposedStep) => void;
  onRemove: () => void;
}) {
  return (
    <div className="space-y-2 rounded-lg bg-warm-fog/5 p-3 ring-1 ring-warm-fog/10">
      <div className="flex items-center justify-between">
        <select
          value={step.kind}
          onChange={(e) => {
            const next: ProposedStep =
              e.target.value === "tool_call"
                ? { kind: "tool_call", tool_name: "", arguments: {} }
                : { kind: "final_answer", text: "" };
            onChange(next);
          }}
          className="rounded bg-carbon px-2 py-1 text-xs text-warm-fog"
        >
          <option value="tool_call">Tool call</option>
          <option value="final_answer">Final answer</option>
        </select>
        <button onClick={onRemove} className="text-xs text-warn">
          Remove
        </button>
      </div>

      {step.kind === "tool_call" ? (
        <>
          <input
            value={step.tool_name}
            onChange={(e) => onChange({ ...step, tool_name: e.target.value })}
            placeholder="tool_name (e.g. search_invoices)"
            className="w-full rounded bg-carbon px-2 py-1 text-xs text-warm-fog"
          />
          <textarea
            value={JSON.stringify(step.arguments, null, 2)}
            onChange={(e) => {
              try {
                onChange({ ...step, arguments: JSON.parse(e.target.value) });
              } catch {
                /* swallow while user types */
              }
            }}
            rows={4}
            className="w-full resize-none rounded bg-carbon px-2 py-1 font-mono text-[0.65rem] text-warm-fog"
            placeholder='{"q": "last month"}'
          />
        </>
      ) : (
        <textarea
          value={step.text}
          onChange={(e) => onChange({ ...step, text: e.target.value })}
          rows={4}
          placeholder="What the agent should have said"
          className="w-full resize-none rounded bg-carbon px-2 py-1 text-xs text-warm-fog"
        />
      )}
    </div>
  );
}
