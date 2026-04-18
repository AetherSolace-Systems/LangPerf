import json

from app.heuristics.types import HeuristicContext, HeuristicHit

THRESHOLD = 3


def _fingerprint(span: dict) -> str:
    kind = span.get("kind") or ""
    name = (span.get("attributes") or {}).get("tool.name") or span.get("name") or ""
    args = (span.get("attributes") or {}).get("tool.arguments") or {}
    try:
        canonical = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        canonical = str(args)
    return f"{kind}:{name}:{canonical}"


class LoopHeuristic:
    slug = "loop"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        counts: dict[str, list[str]] = {}
        for span in ctx.spans:
            if span.get("kind") != "tool":
                continue
            fp = _fingerprint(span)
            counts.setdefault(fp, []).append(span.get("span_id"))
        hits: list[HeuristicHit] = []
        for fp, span_ids in counts.items():
            if len(span_ids) >= THRESHOLD:
                tool = fp.split(":", 2)[1]
                hits.append(
                    HeuristicHit(
                        heuristic=self.slug,
                        severity=min(1.0, len(span_ids) / 10.0),
                        signature=f"{self.slug}:{tool}",
                        details={"tool": tool, "count": len(span_ids), "span_ids": span_ids},
                    )
                )
        return hits
