from datetime import datetime, timezone


async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )


async def test_queue_returns_scored_trajectories(client, session):
    await _bootstrap(client)
    from app.heuristics.engine import evaluate_trajectory
    from app.models import Organization, Span, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    session.add(Span(
        span_id="s1", trace_id="t", trajectory_id=t.id, name="search",
        kind="tool", status_code="ERROR", started_at=datetime.now(timezone.utc),
        attributes={"tool.name": "search"},
        events=[{"name": "exception", "attributes": {"exception.message": "timeout"}}],
    ))
    await session.commit()
    await evaluate_trajectory(session, t.id)

    r = await client.get("/api/queue")
    assert r.status_code == 200
    body = r.json()
    assert body["items"]
    assert body["items"][0]["trajectory_id"] == t.id
    assert body["items"][0]["hits"]


async def test_hits_for_trajectory(client, session):
    await _bootstrap(client)
    from app.heuristics.engine import evaluate_trajectory
    from app.models import Organization, Span, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    session.add(Span(
        span_id="s1", trace_id="t", trajectory_id=t.id, name="x",
        kind="tool", status_code="ERROR", started_at=datetime.now(timezone.utc),
        attributes={"tool.name": "x"}, events=[],
    ))
    await session.commit()
    await evaluate_trajectory(session, t.id)
    r = await client.get(f"/api/queue/{t.id}/hits")
    assert r.status_code == 200
    assert len(r.json()) >= 1
