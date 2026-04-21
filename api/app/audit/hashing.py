"""SHA-256 helpers and RFC 6962 leaf/internal node hashing.

Entry hash binds every immutable field of an audit entry together. Domain
separators (0x00 for leaves, 0x01 for internal nodes) follow RFC 6962 and
prevent leaf/internal pre-image collisions.
"""
from __future__ import annotations

import hashlib

DOMAIN_LEAF = b"\x00"
DOMAIN_INTERNAL = b"\x01"


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def compute_leaf_hash(entry_hash: bytes) -> bytes:
    return sha256(DOMAIN_LEAF + entry_hash)


def compute_internal_hash(left: bytes, right: bytes) -> bytes:
    return sha256(DOMAIN_INTERNAL + left + right)


def compute_entry_hash(
    *,
    seq: int,
    prev_hash: bytes,
    event_hash: bytes,
    agent_id: bytes | None,
    principal_human_id: bytes | None,
    ts_iso: str,
    agent_signature: bytes | None,
    ingest_signature: bytes,
) -> bytes:
    """Hash that links an audit entry into the chain.

    All NULL fields serialize as a single 0x00 byte so that absence vs.
    zero-byte presence is distinguishable.
    """
    def _nullable(b: bytes | None) -> bytes:
        return b"\x00" if b is None else b"\x01" + b

    buf = (
        seq.to_bytes(8, "big")
        + prev_hash
        + event_hash
        + _nullable(agent_id)
        + _nullable(principal_human_id)
        + ts_iso.encode("ascii")
        + _nullable(agent_signature)
        + ingest_signature
    )
    return sha256(buf)
