from datetime import datetime, timezone

import pytest

from app.heuristics.baselines import compute_p95_baselines


@pytest.mark.asyncio
async def test_p95_baselines(session):
    from app.models import Agent, Organization, Span, Trajectory
    org = Organization(name="default", slug="default"); session.add(org); await session.flush()
    agent = Agent(org_id=org.id, signature="sig", name="agent-a", display_name="A")
    session.add(agent); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n", agent_id=agent.id)
    session.add(t); await session.flush()
    now = datetime.now(timezone.utc)
    for i, dur in enumerate([10, 15, 20, 25, 30, 35, 40, 50, 100, 500]):
        session.add(Span(
            span_id=f"s{i}", trace_id="t", trajectory_id=t.id, name="search", kind="tool",
            started_at=now, duration_ms=dur, attributes={"tool.name": "search"},
        ))
    await session.commit()
    baselines = await compute_p95_baselines(session, org.id)
    assert baselines[(agent.id, "search")] > 35
