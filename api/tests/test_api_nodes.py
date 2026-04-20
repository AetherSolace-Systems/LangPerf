from datetime import datetime, timezone


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


async def _seed_trajectory_with_span(session, *, span_id="span-1"):
    from sqlalchemy import select

    from app.models import Organization, Span, Trajectory

    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t)
    await session.flush()
    span = Span(
        span_id=span_id,
        trace_id="t",
        trajectory_id=t.id,
        name="op",
        kind="tool",
        started_at=datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc),
        attributes={"tool.name": "op"},
    )
    session.add(span)
    await session.commit()
    await session.refresh(t)
    await session.refresh(span)
    return t, span


async def test_patch_node_updates_notes(client, session):
    await _bootstrap(client)
    t, span = await _seed_trajectory_with_span(session)

    r = await client.patch(
        f"/api/nodes/{span.span_id}", json={"notes": "hmm, suspicious call"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["span_id"] == span.span_id
    assert body["notes"] == "hmm, suspicious call"

    # Confirm the note rides along on the parent trajectory detail
    got = await client.get(f"/api/trajectories/{t.id}")
    assert got.status_code == 200
    spans = got.json()["spans"]
    target = next(s for s in spans if s["span_id"] == span.span_id)
    assert target["notes"] == "hmm, suspicious call"


async def test_patch_node_clear_notes(client, session):
    await _bootstrap(client)
    _, span = await _seed_trajectory_with_span(session)
    await client.patch(f"/api/nodes/{span.span_id}", json={"notes": "first"})
    r = await client.patch(f"/api/nodes/{span.span_id}", json={"clear_notes": True})
    assert r.status_code == 200
    assert r.json()["notes"] is None


async def test_patch_node_404_for_unknown_span(client):
    await _bootstrap(client)
    r = await client.patch("/api/nodes/does-not-exist", json={"notes": "x"})
    assert r.status_code == 404


async def test_patch_node_requires_auth(client, session):
    # Seed a user + span but do NOT sign the client in — no cookie set.
    from app.models import Organization, Span, Trajectory, User

    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    session.add(
        User(org_id=org.id, email="seed@seed.co", password_hash="x", display_name="Seed")
    )
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t)
    await session.flush()
    session.add(
        Span(
            span_id="lonely-span",
            trace_id="t",
            trajectory_id=t.id,
            name="op",
            started_at=datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc),
            attributes={},
        )
    )
    await session.commit()

    r = await client.patch("/api/nodes/lonely-span", json={"notes": "x"})
    assert r.status_code == 401


async def test_patch_node_org_scoping_hides_other_org(client, session):
    await _bootstrap(client)
    from app.models import Organization, Span, Trajectory

    other = Organization(name="other", slug="other")
    session.add(other)
    await session.flush()
    other_traj = Trajectory(
        org_id=other.id, trace_id="other-t", service_name="svc", name="hidden"
    )
    session.add(other_traj)
    await session.flush()
    session.add(
        Span(
            span_id="other-span",
            trace_id="other-t",
            trajectory_id=other_traj.id,
            name="op",
            started_at=datetime(2026, 4, 19, 12, 0, 0, tzinfo=timezone.utc),
            attributes={},
        )
    )
    await session.commit()

    r = await client.patch("/api/nodes/other-span", json={"notes": "peek"})
    assert r.status_code == 404
