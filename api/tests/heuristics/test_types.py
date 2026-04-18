from app.heuristics.types import HeuristicContext, HeuristicHit


def test_heuristic_hit_is_constructable():
    hit = HeuristicHit(heuristic="tool_error", severity=0.9, signature="tool_error:foo", details={})
    assert hit.heuristic == "tool_error"


def test_heuristic_context_exposes_spans():
    ctx = HeuristicContext(
        trajectory_id="t", org_id="o", spans=[{"span_id": "s1", "name": "x"}], baselines={}
    )
    assert ctx.spans[0]["span_id"] == "s1"
