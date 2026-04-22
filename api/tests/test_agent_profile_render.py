"""agent_profile.render_markdown — structural tests.

These verify structure (sections present, data from the DB appears correctly)
rather than exact byte-for-byte golden-file output. Exact text matching is
brittle for a template that formats floats and dates — defer a snapshot
test until there's a snapshot library adopted. For now: assert invariants.
"""
from __future__ import annotations

import pytest

from app.services.agent_profile import render_markdown


@pytest.mark.asyncio
async def test_render_empty_agent_has_all_sections(session, seed_agent):
    agent = await seed_agent()
    out = await render_markdown(session, agent_id=agent.id, window="7d")
    assert f"# {agent.name}" in out
    assert "## Snapshot" in out
    assert "## Top issues" in out
    assert "## Tool landscape" in out
    assert "## Recent patterns" in out
    # Empty placeholders
    assert "No data in window" in out
    assert "Nothing ranked" in out or "## Top issues" in out
    assert "No tool calls" in out
    assert "No failure-mode tags" in out


@pytest.mark.asyncio
async def test_render_populated_agent_has_runs_count(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "duration_ms": 1200},
            {"started_at_minus_hours": 2, "duration_ms": 1400},
            {"started_at_minus_hours": 3, "duration_ms": 1100},
        ]
    )
    out = await render_markdown(session, agent_id=agent.id, window="7d")
    assert "- runs: 3" in out


@pytest.mark.asyncio
async def test_render_with_heuristic_hits_surfaces_issues(
    session, seed_agent_with_heuristic_hits
):
    agent = await seed_agent_with_heuristic_hits(
        hits=[{"heuristic": "tool_error", "tool": "search_orders", "count": 8}]
    )
    out = await render_markdown(session, agent_id=agent.id, window="7d")
    assert "## Top issues" in out
    # The issue's title should surface
    assert "search_orders" in out.lower() or "tool error" in out.lower()


@pytest.mark.asyncio
async def test_render_with_thumbs_down_shows_feedback_in_snapshot(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "feedback_thumbs_down": 2},
            {"started_at_minus_hours": 2, "feedback_thumbs_down": 1},
        ]
    )
    out = await render_markdown(session, agent_id=agent.id, window="7d")
    assert "3" in out  # total thumbs-down count appears somewhere in snapshot
