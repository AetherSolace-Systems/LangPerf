"""agent_timeseries compute — bucketed metric arrays."""
from __future__ import annotations

import pytest

from app.services.agent_timeseries import compute


@pytest.mark.asyncio
async def test_empty_agent_returns_zero_buckets(session, seed_agent):
    agent = await seed_agent()
    out = await compute(session, agent_id=agent.id, window="7d", metrics=["p95_latency"])
    assert len(out) == 1
    assert out[0]["metric"] == "p95_latency"
    assert out[0]["window"] == "7d"
    assert len(out[0]["buckets"]) > 0
    assert all(b["value"] is None or b["value"] == 0 for b in out[0]["buckets"])


@pytest.mark.asyncio
async def test_p95_latency_reflects_trajectory_durations(
    session, seed_agent_with_trajectories
):
    from tests.conftest import USING_POSTGRES
    if not USING_POSTGRES:
        pytest.skip("percentile_cont requires postgres")

    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 2, "duration_ms": 500},
            {"started_at_minus_hours": 2, "duration_ms": 1500},
            {"started_at_minus_hours": 2, "duration_ms": 2500},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="24h", metrics=["p95_latency"])
    latency = out[0]
    non_null = [b for b in latency["buckets"] if b["value"] is not None]
    assert non_null, "expected at least one non-null bucket"
    assert max(b["value"] for b in non_null) >= 2400


@pytest.mark.asyncio
async def test_feedback_metric_counts_thumbs_down_trajectories(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "feedback_thumbs_down": 2},
            {"started_at_minus_hours": 1, "feedback_thumbs_down": 0},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="24h", metrics=["feedback_down"])
    non_null = [b for b in out[0]["buckets"] if b["value"]]
    assert sum(b["value"] for b in non_null) == 1


@pytest.mark.asyncio
async def test_step_ms_matches_window(session, seed_agent):
    agent = await seed_agent()
    out_24h = await compute(session, agent_id=agent.id, window="24h", metrics=["p95_latency"])
    out_7d = await compute(session, agent_id=agent.id, window="7d", metrics=["p95_latency"])
    out_30d = await compute(session, agent_id=agent.id, window="30d", metrics=["p95_latency"])
    assert out_24h[0]["step_ms"] == 5 * 60 * 1000
    assert out_7d[0]["step_ms"] == 60 * 60 * 1000
    assert out_30d[0]["step_ms"] == 6 * 60 * 60 * 1000


@pytest.mark.asyncio
async def test_completion_rate_excludes_null_completed(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "completed": True},
            {"started_at_minus_hours": 1, "completed": False},
            {"started_at_minus_hours": 1, "completed": None},  # legacy, excluded
        ]
    )
    out = await compute(session, agent_id=agent.id, window="24h", metrics=["completion_rate"])
    non_null = [b for b in out[0]["buckets"] if b["value"] is not None]
    assert non_null, "expected at least one non-null bucket"
    assert non_null[-1]["value"] == pytest.approx(0.5, abs=0.01)
