from app.heuristics.low_confidence import LowConfidenceHeuristic
from app.heuristics.types import HeuristicContext


def test_flags_refusal_finish_reason():
    spans = [{"span_id": "s", "kind": "llm", "attributes": {"gen_ai.response.finish_reason": "content_filter", "gen_ai.response.text": "..."}}]
    hits = LowConfidenceHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={}))
    assert len(hits) == 1


def test_flags_very_short_output():
    spans = [{"span_id": "s", "kind": "llm", "attributes": {"gen_ai.response.finish_reason": "stop", "gen_ai.response.text": "ok"}}]
    hits = LowConfidenceHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={}))
    assert len(hits) == 1
