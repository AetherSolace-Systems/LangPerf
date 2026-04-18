from sqlalchemy import select

from app.models import Agent, Organization, Trajectory, User


async def test_list_trajectories_scoped_to_current_org(client, session):
    # Bootstrap user in org A
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )
    # Now seed a second org with a trajectory — user A should NOT see it
    other_org = Organization(name="other", slug="other")
    session.add(other_org)
    await session.flush()
    session.add(Trajectory(org_id=other_org.id, trace_id="hidden", service_name="svc", name="hidden"))
    await session.commit()

    r = await client.get("/api/trajectories")
    assert r.status_code == 200
    body = r.json()
    names = [t["name"] for t in (body.get("items") if isinstance(body, dict) else body)]
    assert "hidden" not in names


async def test_list_agents_scoped_to_current_org(client, session):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw12345678", "display_name": "A"},
    )
    other_org = Organization(name="other", slug="other")
    session.add(other_org)
    await session.flush()
    session.add(Agent(org_id=other_org.id, signature="hidden-sig", name="hidden-agent", display_name="Hidden"))
    await session.commit()

    r = await client.get("/api/agents")
    assert r.status_code == 200
    body = r.json()
    names = [a["name"] for a in (body.get("items") if isinstance(body, dict) else body)]
    assert "hidden-agent" not in names


async def test_unauthenticated_gets_401(client, session):
    # Seed a user so we're in multi-user mode
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    session.add(User(org_id=org.id, email="seed@seed.co", password_hash="x", display_name="Seed"))
    await session.commit()

    r = await client.get("/api/trajectories")
    assert r.status_code == 401
