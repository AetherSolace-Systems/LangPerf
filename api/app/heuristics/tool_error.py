from app.heuristics.types import HeuristicContext, HeuristicHit


class ToolErrorHeuristic:
    slug = "tool_error"

    def evaluate(self, ctx: HeuristicContext) -> list[HeuristicHit]:
        hits: list[HeuristicHit] = []
        for span in ctx.spans:
            if span.get("kind") != "tool":
                continue
            if (span.get("status_code") or "").upper() != "ERROR":
                continue
            tool_name = (span.get("attributes") or {}).get("tool.name") or span.get("name") or "unknown"
            message = ""
            for ev in span.get("events") or []:
                if (ev.get("name") or "") == "exception":
                    message = (ev.get("attributes") or {}).get("exception.message") or ""
                    break
            hits.append(
                HeuristicHit(
                    heuristic=self.slug,
                    severity=0.8,
                    signature=f"{self.slug}:{tool_name}",
                    details={"tool": tool_name, "message": message, "span_id": span.get("span_id")},
                )
            )
        return hits
