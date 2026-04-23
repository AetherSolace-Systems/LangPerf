"""Worklist end-to-end — seed signals, assert ranking."""
from __future__ import annotations

import pytest

from app.services.agent_worklist import compute


@pytest.mark.asyncio
async def test_empty_agent_returns_empty_list(session, seed_agent):
    agent = await seed_agent()
    out = await compute(session, agent_id=agent.id, window="7d")
    assert out == []


@pytest.mark.asyncio
async def test_tool_error_heuristic_surfaces(
    session, seed_agent_with_heuristic_hits
):
    agent = await seed_agent_with_heuristic_hits(
        hits=[{"heuristic": "tool_error", "tool": "search_orders", "count": 12}]
    )
    out = await compute(session, agent_id=agent.id, window="7d")
    assert len(out) >= 1
    top = out[0]
    assert top["signal"] == "heuristic:tool_error"
    assert "search_orders" in top["title"].lower()
    assert top["affected_runs"] == 12
    assert top["urgency"] in ("high", "med", "low")


@pytest.mark.asyncio
async def test_thumbs_down_surfaces(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "feedback_thumbs_down": 1},
            {"started_at_minus_hours": 2, "feedback_thumbs_down": 3},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="7d")
    signals = [x["signal"] for x in out]
    assert "feedback:thumbs_down" in signals


@pytest.mark.asyncio
async def test_ranking_respects_severity_and_affected_runs(
    session, seed_agent_with_heuristic_hits
):
    agent = await seed_agent_with_heuristic_hits(
        hits=[
            {"heuristic": "apology_phrase", "tool": None, "count": 50},
            {"heuristic": "tool_error", "tool": "send_email", "count": 5},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="7d")
    # tool_error (SEVERITY=3) × log2(6) ≈ 7.75 beats apology_phrase (SEVERITY=1) × log2(51) ≈ 5.67
    assert out[0]["signal"] == "heuristic:tool_error"
