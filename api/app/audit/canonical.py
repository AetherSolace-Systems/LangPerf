"""JCS (RFC 8785) canonical encoding.

The canonicalizer is the stable wire contract for audit-chain signatures.
Any change invalidates historical signatures — gate edits behind the
golden-file tests in ``tests/audit/test_canonical.py``.
"""
from __future__ import annotations

import hashlib
import unicodedata
from typing import Any

import rfc8785


def _nfc(obj: Any) -> Any:
    """Normalize all strings in the payload tree to Unicode NFC."""
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        return {_nfc(k): _nfc(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_nfc(v) for v in obj]
    return obj


def canonical_encode(payload: dict) -> bytes:
    """Return JCS-canonical bytes for ``payload``. NFC-normalized."""
    return rfc8785.dumps(_nfc(payload))


def canonical_hash(payload: dict) -> bytes:
    """SHA-256 of ``canonical_encode(payload)``."""
    return hashlib.sha256(canonical_encode(payload)).digest()
