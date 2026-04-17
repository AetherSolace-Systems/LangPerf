import type { AgentPromptRow } from "@/lib/api";
import { ClientTime } from "@/components/client-time";

export function PromptsView({ prompts }: { prompts: AgentPromptRow[] }) {
  if (prompts.length === 0) {
    return (
      <div className="text-patina text-[12px] p-[16px]">
        No system prompts captured yet. Prompts are extracted from the first
        LLM span of each run.
      </div>
    );
  }
  const total = prompts.reduce((s, p) => s + p.runs, 0);
  return (
    <div className="flex flex-col gap-[10px]">
      {prompts.map((p, i) => {
        const share = total ? (p.runs / total) * 100 : 0;
        const current = i === 0;
        return (
          <div
            key={`${p.first_seen_at}:${i}`}
            className={`border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] ${
              current ? "border-l-2 border-l-aether-teal" : ""
            }`}
          >
            <div className="flex items-center gap-[10px] px-[12px] py-[8px] border-b border-[color:var(--border)]">
              <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-patina">
                {current ? (
                  <span className="text-aether-teal">current</span>
                ) : (
                  `version ${prompts.length - i}`
                )}
              </span>
              <span className="flex-1" />
              <span className="font-mono text-[10px] text-patina">
                {p.runs.toLocaleString()} run{p.runs === 1 ? "" : "s"} · {share.toFixed(0)}% ·{" "}
                first <ClientTime iso={p.first_seen_at} /> · last{" "}
                <ClientTime iso={p.last_seen_at} />
              </span>
            </div>
            <pre className="px-[12px] py-[10px] text-[12px] text-warm-fog whitespace-pre-wrap leading-[1.55] font-mono overflow-x-auto">
              {p.text}
            </pre>
          </div>
        );
      })}
    </div>
  );
}
