import pytest

from app.auth.agent_token import (
    TOKEN_PREFIX_LEN,
    generate_token,
    hash_token,
    verify_token,
)


def test_generate_token_shape():
    token, prefix = generate_token()
    assert token.startswith("lp_")
    # lp_ + 8-char id + _ + 32-char random
    assert len(token) == 3 + 8 + 1 + 32
    assert token[:TOKEN_PREFIX_LEN] == prefix
    assert len(prefix) == TOKEN_PREFIX_LEN


def test_hash_and_verify_roundtrip():
    token, _ = generate_token()
    digest = hash_token(token)
    assert verify_token(token, digest) is True
    assert verify_token(token + "x", digest) is False


def test_generate_token_is_unique():
    seen = set()
    for _ in range(50):
        t, _ = generate_token()
        assert t not in seen
        seen.add(t)
