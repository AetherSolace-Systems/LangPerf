from app.heuristics.latency_outlier import LatencyOutlierHeuristic
from app.heuristics.types import HeuristicContext


def test_flags_span_exceeding_p95_by_margin():
    ctx = HeuristicContext(
        trajectory_id="t", org_id="o",
        spans=[{"span_id": "s1", "kind": "tool", "name": "search", "duration_ms": 5000, "attributes": {"tool.name": "search"}}],
        baselines={"search": 100.0},
    )
    hits = LatencyOutlierHeuristic().evaluate(ctx)
    assert len(hits) == 1
    assert hits[0].heuristic == "latency_outlier"


def test_no_flag_within_p95_margin():
    ctx = HeuristicContext(
        trajectory_id="t", org_id="o",
        spans=[{"span_id": "s1", "kind": "tool", "name": "search", "duration_ms": 120, "attributes": {"tool.name": "search"}}],
        baselines={"search": 100.0},
    )
    assert LatencyOutlierHeuristic().evaluate(ctx) == []
