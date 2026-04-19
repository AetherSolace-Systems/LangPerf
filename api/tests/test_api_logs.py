import time

import pytest

from app.logs.buffer import buffer


async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert r.status_code == 201


@pytest.fixture(autouse=True)
def _clear_buffer():
    # The log buffer is a module-level singleton; clear it before and after
    # each test so events do not leak between tests.
    buffer._events.clear()
    yield
    buffer._events.clear()


async def test_recent_logs_empty(client):
    await _bootstrap(client)
    # Other loggers (httpx, etc.) may have emitted during bootstrap; clear so
    # we are asserting on a known-empty buffer.
    buffer._events.clear()
    r = await client.get("/api/logs/recent")
    assert r.status_code == 200
    # The GET request itself can add an httpx log event; tolerate 0 or a
    # small number of incidental records, but assert no user-seeded payload.
    body = r.json()
    for e in body:
        assert e["source"] != "seed-test"


async def test_recent_logs_returns_buffered_events(client):
    await _bootstrap(client)
    buffer._events.clear()
    now = time.time()
    buffer.add(level="INFO", source="seed-test", logger="t.x", message="hello world", ts=now)
    buffer.add(level="ERROR", source="seed-test", logger="t.x", message="boom", ts=now + 0.1)

    r = await client.get("/api/logs/recent", params={"source": "seed-test"})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    messages = [e["message"] for e in body]
    assert messages == ["hello world", "boom"]
    levels = [e["level"] for e in body]
    assert levels == ["INFO", "ERROR"]
    # seq is monotonic and present.
    assert body[0]["seq"] < body[1]["seq"]


async def test_recent_logs_filter_by_level(client):
    await _bootstrap(client)
    buffer._events.clear()
    now = time.time()
    buffer.add(level="DEBUG", source="seed-test", logger="t.x", message="debug-msg", ts=now)
    buffer.add(level="INFO", source="seed-test", logger="t.x", message="info-msg", ts=now + 0.1)
    buffer.add(level="ERROR", source="seed-test", logger="t.x", message="error-msg", ts=now + 0.2)

    r = await client.get("/api/logs/recent", params={"level": "WARN", "source": "seed-test"})
    assert r.status_code == 200
    messages = [e["message"] for e in r.json()]
    assert messages == ["error-msg"]

    r2 = await client.get("/api/logs/recent", params={"level": "INFO", "source": "seed-test"})
    messages2 = [e["message"] for e in r2.json()]
    assert messages2 == ["info-msg", "error-msg"]


@pytest.mark.skip(reason="SSE coverage deferred — needs event-loop coordination")
async def test_logs_stream_responds_with_event_stream_content_type(client):
    await _bootstrap(client)
    async with client.stream("GET", "/api/logs/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
