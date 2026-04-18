from app.heuristics.loop import LoopHeuristic
from app.heuristics.types import HeuristicContext


def test_detects_loop_of_repeated_tool_calls():
    spans = [
        {"span_id": f"s{i}", "kind": "tool", "name": "search", "attributes": {"tool.name": "search", "tool.arguments": {"q": "foo"}}}
        for i in range(4)
    ]
    hits = LoopHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={}))
    assert len(hits) == 1
    assert hits[0].details["count"] == 4


def test_no_loop_below_threshold():
    spans = [
        {"span_id": "s1", "kind": "tool", "name": "search", "attributes": {"tool.name": "search", "tool.arguments": {"q": "foo"}}},
    ]
    assert LoopHeuristic().evaluate(HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={})) == []
