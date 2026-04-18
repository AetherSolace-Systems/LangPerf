from app.heuristics.types import HeuristicContext, HeuristicHit

MARGIN = 2.0


class LatencyOutlierHeuristic:
    slug = "latency_outlier"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        hits: list[HeuristicHit] = []
        for span in ctx.spans:
            if span.get("kind") != "tool":
                continue
            duration = span.get("duration_ms")
            if duration is None:
                continue
            tool = (span.get("attributes") or {}).get("tool.name") or span.get("name") or "unknown"
            baseline = ctx.baselines.get(tool)
            if not baseline or duration < baseline * MARGIN:
                continue
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=min(1.0, duration / max(baseline, 1) / 5.0),
                    signature=f"{self.slug}:{tool}",
                    details={"tool": tool, "duration_ms": duration, "baseline_p95": baseline},
                )
            )
        return hits
