import pytest
from httpx import ASGITransport, AsyncClient

from app import db as db_module
from app.main import app


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


async def test_get_log_forwarding_default(client):
    await _bootstrap(client)
    r = await client.get("/api/settings/log-forwarding")
    assert r.status_code == 200
    body = r.json()
    assert body["file"]["enabled"] is False
    assert body["datadog"]["enabled"] is False
    assert body["loki"]["enabled"] is False
    assert body["otlp"]["enabled"] is False
    assert body["kinds"]["server_logs"] is True
    assert body["kinds"]["trace_events"] is True
    assert body["kinds"]["full_payloads"] is False


async def test_put_log_forwarding_updates_config(client):
    await _bootstrap(client)
    payload = {
        "file": {"enabled": True, "path": "/tmp/lp.jsonl", "rotate_daily": False, "keep_days": 7},
        "kinds": {"server_logs": True, "trace_events": False, "full_payloads": True, "sdk_diagnostics": True},
    }
    r = await client.put("/api/settings/log-forwarding", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["file"]["enabled"] is True
    assert body["file"]["path"] == "/tmp/lp.jsonl"
    assert body["kinds"]["trace_events"] is False
    assert body["kinds"]["full_payloads"] is True
    # Unspecified sections fall back to defaults.
    assert body["datadog"]["enabled"] is False

    got = (await client.get("/api/settings/log-forwarding")).json()
    assert got["file"]["path"] == "/tmp/lp.jsonl"
    assert got["kinds"]["full_payloads"] is True


async def test_put_log_forwarding_persists_across_requests(client, session_factory):
    await _bootstrap(client)
    payload = {"loki": {"enabled": True, "endpoint": "http://loki:3100", "labels": {"env": "dev"}}}
    r = await client.put("/api/settings/log-forwarding", json=payload)
    assert r.status_code == 200

    # Simulate a separate client/request that shares the same DB+app. Reuses
    # the cookie jar so we authenticate as the same user.
    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[db_module.get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", cookies=client.cookies) as c2:
        got = (await c2.get("/api/settings/log-forwarding")).json()
    assert got["loki"]["enabled"] is True
    assert got["loki"]["endpoint"] == "http://loki:3100"
    assert got["loki"]["labels"] == {"env": "dev"}


async def test_put_log_forwarding_validates_schema(client):
    await _bootstrap(client)
    # keep_days must be int; enabled must be bool.
    r = await client.put(
        "/api/settings/log-forwarding",
        json={"file": {"enabled": "nope", "keep_days": "not-a-number"}},
    )
    assert r.status_code == 422


async def test_log_forwarding_requires_auth(client):
    # No bootstrap → no session cookie.
    r = await client.get("/api/settings/log-forwarding")
    assert r.status_code == 401
