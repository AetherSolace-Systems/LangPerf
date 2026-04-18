from datetime import datetime, timezone


async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )


async def test_clusters_group_trajectories_by_signature(client, session):
    await _bootstrap(client)
    from app.heuristics.engine import evaluate_trajectory
    from app.models import Organization, Span, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    now = datetime.now(timezone.utc)
    for i in range(3):
        t = Trajectory(org_id=org.id, trace_id=f"t{i}", service_name="svc", name=f"n{i}")
        session.add(t); await session.flush()
        session.add(Span(
            span_id=f"s{i}", trace_id=f"t{i}", trajectory_id=t.id, name="search",
            kind="tool", status_code="ERROR", started_at=now,
            attributes={"tool.name": "search"},
            events=[{"name": "exception", "attributes": {"exception.message": "timeout"}}],
        ))
        await session.commit()
        await evaluate_trajectory(session, t.id)

    r = await client.get("/api/clusters")
    body = r.json()
    assert body["clusters"]
    assert body["clusters"][0]["size"] == 3
