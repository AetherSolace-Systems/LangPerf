from app.heuristics.tool_error import ToolErrorHeuristic
from app.heuristics.types import HeuristicContext


def _ctx(spans):
    return HeuristicContext(trajectory_id="t", org_id="o", spans=spans, baselines={})


def test_flags_tool_span_with_error_status():
    spans = [
        {"span_id": "s1", "kind": "tool", "name": "search_orders", "status_code": "ERROR", "attributes": {"tool.name": "search_orders"}, "events": [{"name": "exception", "attributes": {"exception.message": "timeout"}}]},
    ]
    hits = ToolErrorHeuristic().evaluate(_ctx(spans))
    assert len(hits) == 1
    assert hits[0].heuristic == "tool_error"
    assert "search_orders" in hits[0].signature


def test_no_hit_on_ok_tool_spans():
    spans = [{"span_id": "s1", "kind": "tool", "name": "ok_tool", "status_code": "OK", "attributes": {}, "events": []}]
    assert ToolErrorHeuristic().evaluate(_ctx(spans)) == []
