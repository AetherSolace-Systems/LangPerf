from app.heuristics.apology_phrase import ApologyPhraseHeuristic
from app.heuristics.types import HeuristicContext


def _ctx(final_output: str):
    return HeuristicContext(
        trajectory_id="t", org_id="o",
        spans=[
            {"span_id": "s1", "kind": "llm", "attributes": {"gen_ai.response.finish_reason": "stop"}},
            {"span_id": "s2", "kind": "llm", "name": "final", "attributes": {"gen_ai.response.text": final_output}},
        ],
        baselines={},
    )


def test_flags_apology_phrase():
    hits = ApologyPhraseHeuristic().evaluate(_ctx("I'm sorry, I can't help with that."))
    assert len(hits) == 1


def test_no_flag_when_no_apology():
    hits = ApologyPhraseHeuristic().evaluate(_ctx("Here are the results."))
    assert hits == []
