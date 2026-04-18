const COLOR: Record<string, string> = {
  tool_error: "bg-warn/20 text-warn",
  latency_outlier: "bg-peach-neon/20 text-peach-neon",
  apology_phrase: "bg-patina/20 text-patina",
  loop: "bg-peach-neon/20 text-peach-neon",
  low_confidence: "bg-warm-fog/20 text-warm-fog",
};

export function HeuristicBadge({ heuristic }: { heuristic: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[0.65rem] ${COLOR[heuristic] ?? "bg-warm-fog/10 text-warm-fog"}`}>
      {heuristic.replace(/_/g, " ")}
    </span>
  );
}
