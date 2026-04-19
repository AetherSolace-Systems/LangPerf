import pytest


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


@pytest.mark.asyncio
async def test_list_projects_includes_default(client):
    await _bootstrap(client)
    r = await client.get("/api/projects")
    assert r.status_code == 200
    slugs = [p["slug"] for p in r.json()]
    assert "default" in slugs


@pytest.mark.asyncio
async def test_create_project(client):
    await _bootstrap(client)
    r = await client.post(
        "/api/projects",
        json={"name": "Weather Bots", "description": "rain demos", "color": "aether-teal"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "weather-bots"
    assert body["name"] == "Weather Bots"


@pytest.mark.asyncio
async def test_create_duplicate_slug_409(client):
    await _bootstrap(client)
    await client.post("/api/projects", json={"name": "Weather Bots"})
    r = await client.post("/api/projects", json={"name": "Weather Bots"})
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_patch_project(client):
    await _bootstrap(client)
    await client.post("/api/projects", json={"name": "Old"})
    r = await client.patch(
        "/api/projects/old",
        json={"name": "New Name", "description": "updated", "rename_to_slug": "new"},
    )
    assert r.status_code == 200
    assert r.json()["slug"] == "new"


@pytest.mark.asyncio
async def test_delete_default_forbidden(client):
    await _bootstrap(client)
    r = await client.delete("/api/projects/default")
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_delete_empty_project_ok(client):
    await _bootstrap(client)
    await client.post("/api/projects", json={"name": "Empty"})
    r = await client.delete("/api/projects/empty")
    assert r.status_code == 204
