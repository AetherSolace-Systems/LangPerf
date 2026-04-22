"""POST /v1/feedback — bearer auth + trajectory ownership + counter increment."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Trajectory


@pytest.mark.asyncio
async def test_feedback_down_increments_counter(
    client, seed_agent_with_trajectory, session
):
    agent, traj = await seed_agent_with_trajectory()
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "down"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    assert r.status_code == 204
    await session.refresh(traj)
    refreshed = traj
    assert refreshed.feedback_thumbs_down == 1
    assert refreshed.feedback_thumbs_up == 0


@pytest.mark.asyncio
async def test_feedback_up_increments_counter(
    client, seed_agent_with_trajectory, session
):
    agent, traj = await seed_agent_with_trajectory()
    await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "up"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    await session.refresh(traj)
    assert traj.feedback_thumbs_up == 1


@pytest.mark.asyncio
async def test_feedback_appends_note(client, seed_agent_with_trajectory, session):
    agent, traj = await seed_agent_with_trajectory(notes="initial")
    await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "down", "note": "wrong answer"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    await session.refresh(traj)
    assert traj.notes is not None
    assert "initial" in traj.notes
    assert "wrong answer" in traj.notes


@pytest.mark.asyncio
async def test_feedback_rejects_missing_bearer(client, seed_agent_with_trajectory):
    _, traj = await seed_agent_with_trajectory()
    r = await client.post(
        "/v1/feedback", json={"trajectory_id": traj.id, "thumbs": "down"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_feedback_rejects_cross_agent(
    client, seed_agent_with_trajectory, seed_agent
):
    _, traj = await seed_agent_with_trajectory()
    other_agent = await seed_agent()  # different agent, same org
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "down"},
        headers={"Authorization": f"Bearer {other_agent.raw_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_feedback_404_on_missing_trajectory(client, seed_agent):
    agent = await seed_agent()
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": "00000000-0000-0000-0000-000000000000", "thumbs": "down"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_feedback_422_on_invalid_thumbs(client, seed_agent_with_trajectory):
    agent, traj = await seed_agent_with_trajectory()
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "sideways"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    assert r.status_code == 422
