async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )


async def test_assign_reviewer_creates_notification(client, session):
    await _bootstrap(client)
    from app.models import Notification, Organization, Trajectory, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    reviewer = User(org_id=org.id, email="r@r.co", password_hash="x", display_name="R")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([reviewer, t]); await session.commit(); await session.refresh(reviewer); await session.refresh(t)

    r = await client.post(
        f"/api/trajectories/{t.id}/assign",
        json={"user_id": reviewer.id},
    )
    assert r.status_code == 200
    assert r.json()["assigned_user_id"] == reviewer.id

    notifs = (await session.execute(select(Notification).where(Notification.user_id == reviewer.id))).scalars().all()
    assert any(n.kind == "assigned" for n in notifs)


async def test_unassign_reviewer(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    reviewer = User(org_id=org.id, email="r@r.co", password_hash="x", display_name="R")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([reviewer, t]); await session.commit(); await session.refresh(reviewer); await session.refresh(t)
    await client.post(f"/api/trajectories/{t.id}/assign", json={"user_id": reviewer.id})
    r = await client.post(f"/api/trajectories/{t.id}/assign", json={"user_id": None})
    assert r.status_code == 200
    assert r.json()["assigned_user_id"] is None
