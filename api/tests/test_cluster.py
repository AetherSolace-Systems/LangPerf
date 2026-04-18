from app.services.cluster import trajectory_signature


def test_signature_from_hits_is_stable_and_sorted():
    hits = [
        {"heuristic": "tool_error", "signature": "tool_error:search_orders"},
        {"heuristic": "loop", "signature": "loop:search_orders"},
    ]
    a = trajectory_signature(hits)
    b = trajectory_signature(list(reversed(hits)))
    assert a == b
    assert "tool_error:search_orders" in a
