"""Auth enforcement on the OTLP receiver (`POST /v1/traces`).

These tests cover the auth layer only — they don't need a well-formed
OTLP protobuf body; a non-401 status code is sufficient to prove the
bearer token was accepted.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_otlp_rejects_missing_bearer(client):
    r = await client.post(
        "/v1/traces",
        content=b"\x00",
        headers={"content-type": "application/x-protobuf"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_otlp_rejects_unknown_token(client):
    r = await client.post(
        "/v1/traces",
        content=b"\x00",
        headers={
            "content-type": "application/x-protobuf",
            "authorization": "Bearer lp_aaaaaaaa_notarealtokeneverxyz",
        },
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_otlp_accepts_valid_token_and_binds(client, session):
    # bootstrap + create agent
    signup = await client.post(
        "/api/auth/signup",
        json={"email": "a@b.co", "password": "pw-12345678", "display_name": "A"},
    )
    assert signup.status_code == 201

    r = await client.post(
        "/api/agents",
        json={"name": "dog", "language": "python"},
    )
    assert r.status_code == 201
    token = r.json()["token"]

    # A trivially-empty request passes past auth and fails parsing is OK —
    # non-401 from the parser still proves auth succeeded.
    r2 = await client.post(
        "/v1/traces",
        content=b"",
        headers={
            "content-type": "application/x-protobuf",
            "authorization": f"Bearer {token}",
        },
    )
    assert r2.status_code != 401  # passed auth
