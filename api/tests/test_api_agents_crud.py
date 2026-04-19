import pytest


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


async def test_create_agent_returns_token_once(client):
    await _bootstrap(client)
    r = await client.post(
        "/api/agents",
        json={"name": "weather-bot", "language": "python", "description": "demo"},
    )
    assert r.status_code == 201
    body = r.json()
    assert "token" in body
    assert body["token"].startswith("lp_")
    assert body["agent"]["name"] == "weather-bot"
    assert body["agent"]["token_prefix"] is not None
    assert body["agent"]["token_prefix"] == body["token"][:12]

    # Token is only shown once
    listed = (await client.get("/api/agents")).json()
    row = next(a for a in listed if a["name"] == "weather-bot")
    assert "token" not in row
    assert row["token_prefix"] == body["token"][:12]


async def test_create_agent_rejects_duplicate_name(client):
    await _bootstrap(client)
    await client.post("/api/agents", json={"name": "dup", "language": "python"})
    r = await client.post("/api/agents", json={"name": "dup", "language": "python"})
    assert r.status_code == 409


async def test_rotate_token_changes_prefix(client):
    await _bootstrap(client)
    r1 = await client.post("/api/agents", json={"name": "rot", "language": "python"})
    first_prefix = r1.json()["token"][:12]
    r2 = await client.post("/api/agents/rot/rotate-token")
    assert r2.status_code == 200
    second = r2.json()
    assert second["token"].startswith("lp_")
    assert second["token"][:12] != first_prefix


async def test_issue_token_on_legacy_agent(client, session):
    await _bootstrap(client)
    from app.models import Agent, Organization, Project
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    proj = (
        await session.execute(
            select(Project).where(Project.org_id == org.id, Project.slug == "default")
        )
    ).scalar_one()
    session.add(Agent(org_id=org.id, signature="legacy:x", name="legacy-bot", project_id=proj.id))
    await session.commit()

    r = await client.post("/api/agents/legacy-bot/issue-token")
    assert r.status_code == 200
    assert r.json()["token"].startswith("lp_")


async def test_issue_token_rejects_if_already_has_token(client):
    await _bootstrap(client)
    await client.post("/api/agents", json={"name": "has-token", "language": "python"})
    r = await client.post("/api/agents/has-token/issue-token")
    assert r.status_code == 409


async def test_delete_agent(client):
    await _bootstrap(client)
    await client.post("/api/agents", json={"name": "byebye", "language": "python"})
    r = await client.delete("/api/agents/byebye")
    assert r.status_code == 204
    assert (await client.get("/api/agents/byebye")).status_code == 404
