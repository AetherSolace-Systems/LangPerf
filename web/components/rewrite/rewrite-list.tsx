import type { Rewrite } from "@/lib/rewrites";

export function RewriteList({ rewrites }: { rewrites: Rewrite[] }) {
  if (!rewrites.length) {
    return (
      <p className="rounded-lg border border-dashed border-warm-fog/20 p-4 text-center text-xs text-warm-fog/50">
        No rewrites yet. Pick a span in the trajectory and propose one.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {rewrites.map((r) => (
        <li key={r.id} className="rounded-lg border border-warm-fog/10 p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-aether-teal">{r.author_display_name}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[0.65rem] ${
                r.status === "submitted" ? "bg-aether-teal/20 text-aether-teal" : "bg-warm-fog/10 text-warm-fog/60"
              }`}
            >
              {r.status}
            </span>
          </div>
          <p className="mt-1 text-[0.65rem] text-warm-fog/40">Branch: {r.branch_span_id}</p>
          {r.rationale && <p className="mt-2 whitespace-pre-wrap text-sm text-warm-fog">{r.rationale}</p>}
          <ol className="mt-2 space-y-1 text-xs">
            {r.proposed_steps.map((s, i) => (
              <li key={i} className="rounded bg-warm-fog/5 p-2">
                {s.kind === "tool_call" ? (
                  <>
                    <span className="font-mono text-aether-teal">{s.tool_name}</span>
                    <pre className="mt-1 text-[0.65rem] text-warm-fog/70">{JSON.stringify(s.arguments, null, 2)}</pre>
                  </>
                ) : (
                  <p className="text-warm-fog">{s.text}</p>
                )}
              </li>
            ))}
          </ol>
        </li>
      ))}
    </ul>
  );
}
