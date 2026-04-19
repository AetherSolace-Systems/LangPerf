"""Per-agent API token generation + verification.

Tokens are `lp_<8-char-id>_<32-char-random>`. The first 12 characters
(`lp_<8-char-id>`) are the prefix — stored in plaintext on the row, used
to find the agent at auth time. The whole token is bcrypt-hashed for
storage. The raw token is returned once at creation/rotation; after
that only the prefix is displayable.
"""

from __future__ import annotations

import secrets

import bcrypt

TOKEN_PREFIX_LEN = 12  # "lp_" + 8 chars
_ID_ALPHABET = "abcdefghijkmnopqrstuvwxyz23456789"  # no 0/o/1/l to reduce confusion
_RANDOM_LEN = 32


def _random_id(length: int) -> str:
    return "".join(secrets.choice(_ID_ALPHABET) for _ in range(length))


def generate_token() -> tuple[str, str]:
    """Return (raw_token, prefix)."""
    short = _random_id(8)
    random = _random_id(_RANDOM_LEN)
    token = f"lp_{short}_{random}"
    prefix = token[:TOKEN_PREFIX_LEN]
    return token, prefix


def hash_token(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_token(raw: str, digest: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), digest.encode("utf-8"))
    except (ValueError, TypeError):
        return False
