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
        # Two distinct Python keys can be NFC-equal (e.g. decomposed "e\u0301"
        # and composed "\u00e9"). Silently overwriting would be data loss in the
        # wire contract — raise instead so the caller can fix the payload.
        normalized: dict = {}
        for k, v in obj.items():
            nk = _nfc(k)
            if nk in normalized:
                raise ValueError(
                    f"audit payload has keys that collide under Unicode NFC normalization: {nk!r}"
                )
            normalized[nk] = _nfc(v)
        return normalized
    if isinstance(obj, list):
        return [_nfc(v) for v in obj]
    return obj


def canonical_encode(payload: dict) -> bytes:
    """Return JCS-canonical bytes for ``payload``. NFC-normalized."""
    nfc_payload = _nfc(payload)  # raises ValueError on NFC key collisions — let that propagate
    try:
        return rfc8785.dumps(nfc_payload)
    except Exception as exc:
        # rfc8785 raises on NaN / inf / unsupported types (FloatDomainError,
        # etc.). Re-raise with audit-chain context so callers don't need to
        # import the library's exception types, which have varied across versions.
        raise ValueError(f"audit payload is not canonicalizable: {exc}") from exc


def canonical_hash(payload: dict) -> bytes:
    """SHA-256 of ``canonical_encode(payload)``."""
    return hashlib.sha256(canonical_encode(payload)).digest()
