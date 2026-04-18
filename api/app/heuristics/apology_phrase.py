import re

from app.heuristics.types import HeuristicContext, HeuristicHit

PHRASES = [
    r"i'?m sorry",
    r"i apologi[sz]e",
    r"i can'?t (help|assist|do)",
    r"as an ai language model",
    r"i do not have",
    r"unable to (help|assist|provide)",
]
PATTERN = re.compile("|".join(PHRASES), re.IGNORECASE)


class ApologyPhraseHeuristic:
    slug = "apology_phrase"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        final_outputs = []
        for span in ctx.spans:
            if span.get("kind") != "llm":
                continue
            text = (span.get("attributes") or {}).get("gen_ai.response.text")
            if not text:
                continue
            final_outputs.append((span.get("span_id"), text))
        if not final_outputs:
            return []
        span_id, text = final_outputs[-1]
        match = PATTERN.search(text)
        if not match:
            return []
        phrase = match.group(0).lower()
        return [
            HeuristicHit(
                heuristic=self.slug,
                severity=0.6,
                signature=f"{self.slug}:{phrase}",
                details={"phrase": phrase, "span_id": span_id, "excerpt": text[max(0, match.start() - 30):match.end() + 30]},
            )
        ]
