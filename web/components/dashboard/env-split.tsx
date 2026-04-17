import type { EnvSplit } from "@/lib/api";

const COLORS: Record<string, string> = {
  prod: "#6BBAB1",
  staging: "#E8A87C",
  dev: "#7A8B8E",
};

export function EnvSplitCard({ entries }: { entries: EnvSplit[] }) {
  const total = entries.reduce((s, e) => s + e.runs, 0) || 1;
  return (
    <>
      <div className="flex h-[22px] rounded-[2px] overflow-hidden my-[6px] mb-[10px]">
        {entries.map((e) => {
          const pct = (e.runs / total) * 100;
          return (
            <div
              key={e.environment}
              style={{
                width: `${pct}%`,
                background: COLORS[e.environment] ?? "#3A4950",
              }}
              title={`${e.environment}: ${e.runs}`}
            />
          );
        })}
      </div>
      <div className="font-mono text-[10px] text-patina leading-[1.8]">
        {entries.map((e) => {
          const pct = ((e.runs / total) * 100).toFixed(0);
          const dot = COLORS[e.environment] ?? "#3A4950";
          return (
            <div key={e.environment}>
              <span
                style={{
                  background: dot,
                  width: 6,
                  height: 6,
                  display: "inline-block",
                  marginRight: 6,
                }}
              />
              {e.environment} <b className="text-warm-fog font-medium">{pct}%</b> ·{" "}
              {e.runs.toLocaleString()}
            </div>
          );
        })}
      </div>
    </>
  );
}
