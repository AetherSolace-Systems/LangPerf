from app.heuristics.types import HeuristicContext, HeuristicHit

MIN_FINAL_OUTPUT_LEN = 10
REFUSAL_REASONS = {"content_filter", "refusal"}


class LowConfidenceHeuristic:
    slug = "low_confidence"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        llm_spans = [s for s in ctx.spans if s.get("kind") == "llm"]
        if not llm_spans:
            return []
        final = llm_spans[-1]
        attrs = final.get("attributes") or {}
        reason = attrs.get("gen_ai.response.finish_reason")
        text = attrs.get("gen_ai.response.text") or ""
        hits: list[HeuristicHit] = []
        if reason in REFUSAL_REASONS:
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=0.7,
                    signature=f"{self.slug}:{reason}",
                    details={"reason": reason, "span_id": final.get("span_id")},
                )
            )
        elif len(text.strip()) < MIN_FINAL_OUTPUT_LEN:
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=0.4,
                    signature=f"{self.slug}:short_output",
                    details={"length": len(text), "span_id": final.get("span_id")},
                )
            )
        return hits
