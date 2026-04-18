async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )
    assert r.status_code == 201
    return r.json()["user"]


async def _seed_trajectory(session, org_slug="default"):
    from sqlalchemy import select
    from app.models import Organization, Trajectory
    org = (await session.execute(select(Organization).where(Organization.slug == org_slug))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit(); await session.refresh(t)
    return t


async def test_create_comment_on_span(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)

    r = await client.post(
        f"/api/trajectories/{t.id}/nodes/span-1/comments",
        json={"body": "first comment"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["body"] == "first comment"


async def test_list_comments_returns_thread(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)
    await client.post(f"/api/trajectories/{t.id}/nodes/span-1/comments", json={"body": "one"})
    await client.post(f"/api/trajectories/{t.id}/nodes/span-1/comments", json={"body": "two"})
    r = await client.get(f"/api/trajectories/{t.id}/nodes/span-1/comments")
    assert r.status_code == 200
    bodies = [c["body"] for c in r.json()]
    assert bodies == ["one", "two"]


async def test_resolve_comment(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)
    created = await client.post(f"/api/trajectories/{t.id}/nodes/span-1/comments", json={"body": "x"})
    cid = created.json()["id"]
    r = await client.post(f"/api/comments/{cid}/resolve")
    assert r.status_code == 200
    assert r.json()["resolved"] is True


async def test_mention_creates_notification(client, session):
    await _bootstrap(client)
    from sqlalchemy import select
    from app.models import Organization, User
    org = (await session.execute(select(Organization))).scalar_one()
    reviewer = User(org_id=org.id, email="r@r.co", password_hash="x", display_name="Reviewer")
    session.add(reviewer); await session.commit(); await session.refresh(reviewer)
    t = await _seed_trajectory(session)

    r = await client.post(
        f"/api/trajectories/{t.id}/nodes/span-1/comments",
        json={"body": "ping @Reviewer"},
    )
    assert r.status_code == 201
    from app.models import Notification
    notifs = (await session.execute(select(Notification).where(Notification.user_id == reviewer.id))).scalars().all()
    assert len(notifs) == 1
    assert notifs[0].kind == "mention"


async def test_delete_comment(client, session):
    await _bootstrap(client)
    t = await _seed_trajectory(session)
    created = await client.post(f"/api/trajectories/{t.id}/nodes/span-1/comments", json={"body": "x"})
    cid = created.json()["id"]
    r = await client.delete(f"/api/comments/{cid}")
    assert r.status_code == 204
