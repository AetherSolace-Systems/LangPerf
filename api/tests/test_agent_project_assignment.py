import pytest


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


async def test_create_agent_defaults_to_default_project(client):
    await _bootstrap(client)
    r = await client.post("/api/agents", json={"name": "a1", "language": "python"})
    assert r.status_code == 201
    assert r.json()["agent"]["project"]["slug"] == "default"


async def test_create_agent_in_named_project(client):
    await _bootstrap(client)
    await client.post("/api/projects", json={"name": "Bots"})
    r = await client.post(
        "/api/agents",
        json={"name": "a1", "language": "python", "project_slug": "bots"},
    )
    assert r.status_code == 201
    assert r.json()["agent"]["project"]["slug"] == "bots"


async def test_list_agents_filter_by_project(client):
    await _bootstrap(client)
    await client.post("/api/projects", json={"name": "Bots"})
    await client.post("/api/agents", json={"name": "a1", "language": "python"})
    await client.post(
        "/api/agents",
        json={"name": "a2", "language": "python", "project_slug": "bots"},
    )
    all_ = (await client.get("/api/agents")).json()
    assert {a["name"] for a in all_} == {"a1", "a2"}
    bots = (await client.get("/api/agents?project=bots")).json()
    assert {a["name"] for a in bots} == {"a2"}


async def test_patch_agent_moves_project(client):
    await _bootstrap(client)
    await client.post("/api/projects", json={"name": "Bots"})
    await client.post("/api/agents", json={"name": "a1", "language": "python"})
    r = await client.patch("/api/agents/a1", json={"project_slug": "bots"})
    assert r.status_code == 200
    assert r.json()["project"]["slug"] == "bots"


async def test_create_agent_bad_project_404(client):
    await _bootstrap(client)
    r = await client.post(
        "/api/agents",
        json={"name": "a1", "language": "python", "project_slug": "nope"},
    )
    assert r.status_code == 404


async def test_delete_project_with_agents_forbidden(client):
    await _bootstrap(client)
    await client.post("/api/projects", json={"name": "Busy"})
    await client.post(
        "/api/agents",
        json={"name": "bot1", "language": "python", "project_slug": "busy"},
    )
    r = await client.delete("/api/projects/busy")
    assert r.status_code == 409
