import pytest
import pytest_asyncio


async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )


async def test_list_notifications_empty(client):
    await _bootstrap(client)
    r = await client.get("/api/notifications")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_notifications_after_mention(client, session):
    await _bootstrap(client)
    from app.models import Notification, Organization, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    me = (await session.execute(select(User).where(User.email == "a@b.co"))).scalar_one()
    session.add(Notification(org_id=org.id, user_id=me.id, kind="mention", payload={"x": 1}))
    await session.commit()
    r = await client.get("/api/notifications")
    body = r.json()
    assert len(body) == 1
    assert body[0]["kind"] == "mention"


async def test_mark_read(client, session):
    await _bootstrap(client)
    from app.models import Notification, Organization, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    me = (await session.execute(select(User).where(User.email == "a@b.co"))).scalar_one()
    n = Notification(org_id=org.id, user_id=me.id, kind="mention", payload={"x": 1})
    session.add(n); await session.commit(); await session.refresh(n)
    r = await client.post(f"/api/notifications/{n.id}/read")
    assert r.status_code == 204
