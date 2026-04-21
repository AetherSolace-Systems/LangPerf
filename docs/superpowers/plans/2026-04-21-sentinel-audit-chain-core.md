# Sentinel Audit Chain Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the audit-chain foundation from the Sentinel child spec — JCS canonical encoding, cryptographic primitives, data model, `AuditService` with single-Writer batching, RFC 6962 Merkle tree with inclusion/consistency proofs, and pluggable external anchoring (RFC 3161 TSA + offline-file + none). Produces a working, testable signed audit log end-to-end.

**Architecture:** Native Python transparency log. JCS (RFC 8785) canonical encoding, Ed25519 primary + ECDSA P-384 alt for signing, SHA-256 hashing, RFC 6962 Merkle tree. Single Writer per deployment (Postgres advisory-lock leader election, in-process batching with group commit). External anchors behind one pluggable interface. No per-request advisory locks on the hot path.

**Tech Stack:** Python 3.12, FastAPI, async SQLAlchemy 2.0, Alembic, Postgres (sqlite for tests), `rfc8785` library for JCS, `pynacl` for Ed25519, `cryptography` for ECDSA P-384 / SHA-256 / X.509, `asn1crypto` for RFC 3161 TimeStampToken parsing.

**Scope (this plan):** Audit chain core only — Phases A–D from the child spec's implementation sequence. **Out of scope** (separate follow-up plans): agent identity + bootstrap flow, ingest node identity, OTLP ingest wiring, SDK additions, verifier CLI. Each of those builds on the primitives this plan lands.

**Parent spec:** `docs/superpowers/specs/2026-04-21-sentinel-audit-chain-and-agent-identity-design.md`.

---

## File Structure

### New files

```
api/app/audit/
    __init__.py
    canonical.py        # JCS canonical encoding wrapper
    crypto.py           # Ed25519 + ECDSA P-384 signing primitives
    hashing.py          # SHA-256, entry_hash, leaf_hash, internal_hash helpers
    leader.py           # Postgres advisory-lock writer leader election
    writer.py           # Single-Writer batching coroutine
    merkle.py           # RFC 6962 Merkle tree + inclusion/consistency proofs
    anchor/
        __init__.py
        base.py         # ExternalAnchor abstract interface
        none_anchor.py  # Dev-only no-op anchor
        rfc3161.py      # RFC 3161 TSA client
        offline_file.py # Offline file-signer anchor

api/app/models/audit.py       # AuditEntry, AuditRoot, ExternalAnchor, AgentIdentity, IngestNode

api/app/services/audit.py     # AuditService — single mutation entry point

api/alembic/versions/
    0017_sentinel_audit_tables.py       # audit_entries, audit_roots, external_anchors + trigger
    0018_sentinel_agent_identities.py   # agent_identities (shell for Plan 2)
    0019_sentinel_ingest_nodes.py       # ingest_nodes (shell for Plan 2)
    0020_sentinel_audit_entry_refs.py   # audit_entry_id FK columns on existing tables

api/tests/audit/
    __init__.py
    conftest.py
    test_canonical.py
    test_crypto.py
    test_hashing.py
    test_leader.py
    test_writer.py
    test_merkle.py
    test_anchor_base.py
    test_anchor_rfc3161.py
    test_anchor_offline_file.py
    test_audit_service.py
    test_audit_e2e.py
```

### Modified files

- `api/app/models/__init__.py` — export new models so `Base.metadata` sees them.
- `api/pyproject.toml` — add `rfc8785`, `pynacl`, `asn1crypto` dependencies (`cryptography` already present).
- `api/tests/conftest.py` — no change expected; new tests pick up existing fixtures.

### Responsibility split

- `audit/` — pure primitives, no DB access (except `leader.py` which wraps advisory locks).
- `models/audit.py` — SQLAlchemy models only. No business logic.
- `services/audit.py` — the only mutation entry point. Every other service (in Plans 2+) calls `AuditService.append` before persisting its own rows.

---

## Task 1: JCS canonical encoding module

**Files:**
- Create: `api/app/audit/__init__.py`
- Create: `api/app/audit/canonical.py`
- Create: `api/tests/audit/__init__.py`
- Create: `api/tests/audit/test_canonical.py`
- Modify: `api/pyproject.toml` — add `rfc8785>=0.1.4,<0.2`

- [ ] **Step 1: Add the dependency**

Modify `api/pyproject.toml` — under `[project] dependencies`, add:

```toml
"rfc8785>=0.1.4,<0.2",
```

Run: `cd api && uv pip install -e .` (or project-standard install)
Expected: `rfc8785` imports cleanly.

- [ ] **Step 2: Write the failing tests**

Create `api/tests/audit/__init__.py` (empty).

Create `api/tests/audit/test_canonical.py`:

```python
"""JCS (RFC 8785) canonical encoding tests.

Golden-file tests gate every change to the canonicalizer; an accidental
divergence would invalidate every historical signature.
"""
from app.audit.canonical import canonical_encode, canonical_hash


def test_dict_keys_sorted_lexicographically():
    assert canonical_encode({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_nested_dict_keys_sorted():
    assert canonical_encode({"z": {"b": 1, "a": 2}, "a": 3}) == b'{"a":3,"z":{"a":2,"b":1}}'


def test_timestamp_represented_as_iso_string():
    # Timestamps must be strings, not floats — JCS number constraints are too
    # narrow for nanosecond precision and not all OTLP sources emit epoch ms.
    payload = {"ts": "2026-04-21T18:00:00.123456Z", "v": 1}
    assert canonical_encode(payload) == b'{"ts":"2026-04-21T18:00:00.123456Z","v":1}'


def test_unicode_normalized_to_nfc():
    # "é" can be composed (U+00E9) or decomposed (U+0065 U+0301). JCS mandates NFC.
    composed = {"x": "\u00e9"}
    decomposed = {"x": "e\u0301"}
    assert canonical_encode(composed) == canonical_encode(decomposed)


def test_canonical_hash_is_sha256_of_encoding():
    import hashlib
    payload = {"hello": "world"}
    expected = hashlib.sha256(b'{"hello":"world"}').digest()
    assert canonical_hash(payload) == expected


def test_empty_dict_is_valid():
    assert canonical_encode({}) == b"{}"


def test_arrays_preserve_order():
    assert canonical_encode({"xs": [3, 1, 2]}) == b'{"xs":[3,1,2]}'
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_canonical.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.canonical'`.

- [ ] **Step 4: Write the minimal implementation**

Create `api/app/audit/__init__.py` (empty).

Create `api/app/audit/canonical.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass, then commit**

Run: `pytest api/tests/audit/test_canonical.py -v`
Expected: 7 passed.

```bash
git add api/pyproject.toml api/app/audit/__init__.py api/app/audit/canonical.py api/tests/audit/__init__.py api/tests/audit/test_canonical.py
git commit -m "feat(audit): JCS canonical encoding module"
```

---

## Task 2: Signing primitives (Ed25519 + ECDSA P-384)

**Files:**
- Create: `api/app/audit/crypto.py`
- Create: `api/tests/audit/test_crypto.py`
- Modify: `api/pyproject.toml` — add `pynacl>=1.5,<2.0`

- [ ] **Step 1: Add the dependency**

Modify `api/pyproject.toml` under `[project] dependencies`:

```toml
"pynacl>=1.5,<2.0",
```

Run: `cd api && uv pip install -e .`
Expected: `nacl` imports cleanly. (`cryptography` is already a transitive dep.)

- [ ] **Step 2: Write the failing tests**

Create `api/tests/audit/test_crypto.py`:

```python
"""Signing primitive tests — Ed25519 + ECDSA P-384 round-trips."""
import pytest
from app.audit.crypto import (
    SIG_ECDSA_P384,
    SIG_ED25519,
    VerifyError,
    generate_keypair,
    load_public_key,
    sign,
    verify,
)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_generate_sign_verify_roundtrip(alg):
    priv, pub = generate_keypair(alg)
    data = b"the quick brown fox"
    sig = sign(priv, data, alg)
    # verify() returns None on success, raises on failure
    verify(pub, sig, data, alg)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_verify_rejects_tampered_data(alg):
    priv, pub = generate_keypair(alg)
    sig = sign(priv, b"original", alg)
    with pytest.raises(VerifyError):
        verify(pub, sig, b"tampered", alg)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_verify_rejects_wrong_key(alg):
    _, pub_a = generate_keypair(alg)
    priv_b, _ = generate_keypair(alg)
    sig_b = sign(priv_b, b"data", alg)
    with pytest.raises(VerifyError):
        verify(pub_a, sig_b, b"data", alg)


@pytest.mark.parametrize("alg", [SIG_ED25519, SIG_ECDSA_P384])
def test_public_key_roundtrip_through_serialization(alg):
    _, pub = generate_keypair(alg)
    serialized = bytes(pub)
    restored = load_public_key(serialized, alg)
    assert bytes(restored) == serialized


def test_unknown_algorithm_raises():
    priv, _ = generate_keypair(SIG_ED25519)
    with pytest.raises(ValueError, match="unknown algorithm"):
        sign(priv, b"x", "not-an-alg")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_crypto.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.crypto'`.

- [ ] **Step 4: Write the minimal implementation**

Create `api/app/audit/crypto.py`:

```python
"""Signing primitives for the audit chain.

Ed25519 is primary (FIPS 186-5 approved). ECDSA P-384 is pluggable for
legacy FIPS environments. Vetted libraries only: ``pynacl`` for Ed25519,
``cryptography`` for P-384. Never roll our own.
"""
from __future__ import annotations

from typing import Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey as NaclSigningKey
from nacl.signing import VerifyKey as NaclVerifyKey

SIG_ED25519 = "ed25519"
SIG_ECDSA_P384 = "ecdsa-p384"

_P384_CURVE = ec.SECP384R1()


class VerifyError(Exception):
    """Signature verification failed."""


def generate_keypair(alg: str) -> Tuple[bytes, bytes]:
    """Return ``(private_bytes, public_bytes)`` for ``alg``."""
    if alg == SIG_ED25519:
        priv = NaclSigningKey.generate()
        return bytes(priv), bytes(priv.verify_key)
    if alg == SIG_ECDSA_P384:
        priv = ec.generate_private_key(_P384_CURVE)
        priv_bytes = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_bytes = priv.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return priv_bytes, pub_bytes
    raise ValueError(f"unknown algorithm: {alg!r}")


def load_public_key(public_bytes: bytes, alg: str):
    """Rehydrate a public key object from its serialized bytes."""
    if alg == SIG_ED25519:
        return NaclVerifyKey(public_bytes)
    if alg == SIG_ECDSA_P384:
        return serialization.load_pem_public_key(public_bytes)
    raise ValueError(f"unknown algorithm: {alg!r}")


def sign(private_bytes: bytes, data: bytes, alg: str) -> bytes:
    """Return a signature over ``data`` using the private key."""
    if alg == SIG_ED25519:
        return bytes(NaclSigningKey(private_bytes).sign(data).signature)
    if alg == SIG_ECDSA_P384:
        priv = serialization.load_pem_private_key(private_bytes, password=None)
        return priv.sign(data, ec.ECDSA(hashes.SHA384()))
    raise ValueError(f"unknown algorithm: {alg!r}")


def verify(public_bytes: bytes, signature: bytes, data: bytes, alg: str) -> None:
    """Raise ``VerifyError`` if ``signature`` does not verify ``data``."""
    if alg == SIG_ED25519:
        try:
            NaclVerifyKey(public_bytes).verify(data, signature)
        except BadSignatureError as exc:
            raise VerifyError("ed25519 signature invalid") from exc
        return
    if alg == SIG_ECDSA_P384:
        pub = serialization.load_pem_public_key(public_bytes)
        try:
            pub.verify(signature, data, ec.ECDSA(hashes.SHA384()))
        except InvalidSignature as exc:
            raise VerifyError("ecdsa-p384 signature invalid") from exc
        return
    raise ValueError(f"unknown algorithm: {alg!r}")
```

- [ ] **Step 5: Run tests to verify they pass, then commit**

Run: `pytest api/tests/audit/test_crypto.py -v`
Expected: 9 passed (7 parametrized + 2 singletons).

```bash
git add api/pyproject.toml api/app/audit/crypto.py api/tests/audit/test_crypto.py
git commit -m "feat(audit): Ed25519 + ECDSA P-384 signing primitives"
```

---

## Task 3: Hash + entry-hash helpers

**Files:**
- Create: `api/app/audit/hashing.py`
- Create: `api/tests/audit/test_hashing.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/audit/test_hashing.py`:

```python
"""Hashing helpers — SHA-256 wrappers + RFC 6962 leaf/internal + entry_hash."""
import hashlib

from app.audit.hashing import (
    DOMAIN_INTERNAL,
    DOMAIN_LEAF,
    compute_entry_hash,
    compute_internal_hash,
    compute_leaf_hash,
    sha256,
)


def test_sha256_is_standard():
    assert sha256(b"abc") == hashlib.sha256(b"abc").digest()


def test_leaf_hash_prepends_zero_domain_separator():
    leaf_data = bytes.fromhex("aa" * 32)
    assert compute_leaf_hash(leaf_data) == hashlib.sha256(b"\x00" + leaf_data).digest()
    assert DOMAIN_LEAF == b"\x00"


def test_internal_hash_prepends_one_domain_separator():
    left = bytes.fromhex("aa" * 32)
    right = bytes.fromhex("bb" * 32)
    expected = hashlib.sha256(b"\x01" + left + right).digest()
    assert compute_internal_hash(left, right) == expected
    assert DOMAIN_INTERNAL == b"\x01"


def test_leaf_and_internal_cannot_collide():
    # Domain separators prevent pre-image attacks between leaves and internal nodes.
    data = bytes.fromhex("cc" * 32)
    assert compute_leaf_hash(data) != compute_internal_hash(data[:16], data[16:])


def test_compute_entry_hash_is_stable_for_stable_inputs():
    h1 = compute_entry_hash(
        seq=42,
        prev_hash=bytes(32),
        event_hash=b"\xaa" * 32,
        agent_id=b"\xbb" * 16,
        principal_human_id=None,
        ts_iso="2026-04-21T00:00:00Z",
        agent_signature=b"\xcc" * 64,
        ingest_signature=b"\xdd" * 64,
    )
    h2 = compute_entry_hash(
        seq=42,
        prev_hash=bytes(32),
        event_hash=b"\xaa" * 32,
        agent_id=b"\xbb" * 16,
        principal_human_id=None,
        ts_iso="2026-04-21T00:00:00Z",
        agent_signature=b"\xcc" * 64,
        ingest_signature=b"\xdd" * 64,
    )
    assert h1 == h2


def test_compute_entry_hash_changes_if_any_input_changes():
    base = dict(
        seq=1,
        prev_hash=bytes(32),
        event_hash=b"\xaa" * 32,
        agent_id=None,
        principal_human_id=None,
        ts_iso="2026-04-21T00:00:00Z",
        agent_signature=None,
        ingest_signature=b"\xdd" * 64,
    )
    h_base = compute_entry_hash(**base)
    for field, new_value in [
        ("seq", 2),
        ("prev_hash", b"\xff" * 32),
        ("event_hash", b"\x00" * 32),
        ("ts_iso", "2026-04-22T00:00:00Z"),
        ("ingest_signature", b"\x00" * 64),
    ]:
        mutated = {**base, field: new_value}
        assert compute_entry_hash(**mutated) != h_base, f"{field} should affect entry_hash"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_hashing.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.hashing'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/app/audit/hashing.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_hashing.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/audit/hashing.py api/tests/audit/test_hashing.py
git commit -m "feat(audit): SHA-256 + RFC 6962 leaf/internal + entry-hash helpers"
```

---

## Task 4: Migration 0017 — audit tables + append-only trigger

**Files:**
- Create: `api/alembic/versions/0017_sentinel_audit_tables.py`
- Create: `api/tests/audit/test_migration_append_only.py`

- [ ] **Step 1: Write the migration**

Create `api/alembic/versions/0017_sentinel_audit_tables.py`:

```python
"""sentinel audit tables

Revision ID: 0017_sentinel_audit_tables
Revises: 0016_projects
Create Date: 2026-04-21 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0017_sentinel_audit_tables"
down_revision = "0016_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_entries",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("seq", sa.BigInteger, nullable=False, unique=True),
        sa.Column("prev_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_payload", sa.LargeBinary, nullable=False),
        sa.Column("event_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("entry_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("agent_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("principal_human_id", PgUUID(as_uuid=True), nullable=True),
        sa.Column("agent_signature", sa.LargeBinary, nullable=True),
        sa.Column("ingest_node_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("ingest_signature", sa.LargeBinary, nullable=False),
        sa.Column(
            "ts",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("agent_ts", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audit_entries_event_type_ts", "audit_entries", ["event_type", "ts"])
    op.create_index("ix_audit_entries_agent_id_ts", "audit_entries", ["agent_id", "ts"])
    op.create_index(
        "ix_audit_entries_principal_human_id_ts",
        "audit_entries",
        ["principal_human_id", "ts"],
    )

    # Append-only trigger: reject UPDATE and DELETE on audit_entries.
    # Postgres-only; sqlite tests rely on application-level enforcement.
    if op.get_context().dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION audit_entries_append_only() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_entries is append-only';
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER audit_entries_no_update
                BEFORE UPDATE ON audit_entries
                FOR EACH ROW EXECUTE FUNCTION audit_entries_append_only();

            CREATE TRIGGER audit_entries_no_delete
                BEFORE DELETE ON audit_entries
                FOR EACH ROW EXECUTE FUNCTION audit_entries_append_only();
            """
        )

    op.create_table(
        "audit_roots",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tree_size", sa.BigInteger, nullable=False, unique=True),
        sa.Column("root_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingest_node_id", PgUUID(as_uuid=True), nullable=False),
        sa.Column("ingest_signature", sa.LargeBinary, nullable=False),
    )

    op.create_table(
        "external_anchors",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "root_id",
            sa.BigInteger,
            sa.ForeignKey("audit_roots.id"),
            nullable=False,
        ),
        sa.Column("anchor_type", sa.String(32), nullable=False),
        sa.Column("anchor_payload", sa.LargeBinary, nullable=False),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anchor_ref", sa.Text, nullable=True),
    )
    op.create_index("ix_external_anchors_root_id", "external_anchors", ["root_id"])


def downgrade() -> None:
    if op.get_context().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_entries_no_delete ON audit_entries;")
        op.execute("DROP TRIGGER IF EXISTS audit_entries_no_update ON audit_entries;")
        op.execute("DROP FUNCTION IF EXISTS audit_entries_append_only();")
    op.drop_index("ix_external_anchors_root_id", table_name="external_anchors")
    op.drop_table("external_anchors")
    op.drop_table("audit_roots")
    op.drop_index("ix_audit_entries_principal_human_id_ts", table_name="audit_entries")
    op.drop_index("ix_audit_entries_agent_id_ts", table_name="audit_entries")
    op.drop_index("ix_audit_entries_event_type_ts", table_name="audit_entries")
    op.drop_table("audit_entries")
```

- [ ] **Step 2: Write a test that the migration applies cleanly**

Create `api/tests/audit/test_migration_append_only.py`:

```python
"""Verify the 0017 migration creates tables and the append-only trigger."""
import os

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

USING_POSTGRES = os.environ.get("TEST_DATABASE_URL", "").startswith("postgres")


@pytest.mark.asyncio
async def test_audit_tables_exist():
    """Base.metadata.create_all() covers this at session start; just assert shape."""
    from app.db import SessionLocal

    async with SessionLocal() as session:
        # Count rows to prove SELECTing works without error.
        await session.execute(sa.text("SELECT COUNT(*) FROM audit_entries"))
        await session.execute(sa.text("SELECT COUNT(*) FROM audit_roots"))
        await session.execute(sa.text("SELECT COUNT(*) FROM external_anchors"))


@pytest.mark.asyncio
@pytest.mark.skipif(not USING_POSTGRES, reason="append-only trigger is Postgres-only")
async def test_audit_entries_update_rejected():
    from app.db import SessionLocal

    async with SessionLocal() as session:
        await session.execute(
            sa.text(
                """
                INSERT INTO audit_entries
                    (seq, prev_hash, event_type, event_payload, event_hash, entry_hash,
                     ingest_node_id, ingest_signature)
                VALUES
                    (0, :zero, 'genesis', :payload, :zero, :zero,
                     '00000000-0000-0000-0000-000000000000', :zero)
                """
            ),
            {"zero": bytes(32), "payload": b"{}"},
        )
        await session.commit()
        with pytest.raises(Exception, match="append-only"):
            await session.execute(
                sa.text("UPDATE audit_entries SET event_type = 'x' WHERE seq = 0")
            )
            await session.commit()
```

- [ ] **Step 3: Run tests to verify behavior**

Run: `pytest api/tests/audit/test_migration_append_only.py -v`
Expected: Under sqlite (default) — 1 passed, 1 skipped. Under Postgres — 2 passed.

- [ ] **Step 4: Commit**

```bash
git add api/alembic/versions/0017_sentinel_audit_tables.py api/tests/audit/test_migration_append_only.py
git commit -m "feat(audit): 0017 migration — audit_entries/roots/anchors + append-only trigger"
```

---

## Task 5: Migration 0018 — agent_identities (shell)

**Files:**
- Create: `api/alembic/versions/0018_sentinel_agent_identities.py`

> This is a shell migration. Full service implementation lands in Plan 2; we create the table now so `audit_entries.agent_id` has a valid FK target.

- [ ] **Step 1: Write the migration**

Create `api/alembic/versions/0018_sentinel_agent_identities.py`:

```python
"""sentinel agent_identities (shell — service lands in Plan 2)

Revision ID: 0018_sentinel_agent_identities
Revises: 0017_sentinel_audit_tables
Create Date: 2026-04-21 12:01:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0018_sentinel_agent_identities"
down_revision = "0017_sentinel_audit_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_identities",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False, unique=True),
        sa.Column("public_key_alg", sa.String(32), nullable=False),
        sa.Column("config_hash", sa.LargeBinary(32), nullable=False),
        sa.Column("config_ref", sa.Text, nullable=False),
        sa.Column(
            "tenant_id",
            PgUUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "owner_human_id",
            PgUUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "issuance_audit_entry_id",
            sa.BigInteger,
            sa.ForeignKey("audit_entries.id"),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revocation_audit_entry_id",
            sa.BigInteger,
            sa.ForeignKey("audit_entries.id"),
            nullable=True,
        ),
        sa.Column("revocation_reason", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_agent_identities_config_hash_tenant",
        "agent_identities",
        ["config_hash", "tenant_id"],
    )
    op.create_index(
        "ix_agent_identities_owner_human_id",
        "agent_identities",
        ["owner_human_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_agent_identities_owner_human_id", table_name="agent_identities")
    op.drop_index("ix_agent_identities_config_hash_tenant", table_name="agent_identities")
    op.drop_table("agent_identities")
```

- [ ] **Step 2: Run migrations to verify**

Run: `pytest api/tests/audit/test_migration_append_only.py -v`
Expected: Still passing — new migration doesn't break prior checks. (Full tests for this table arrive in Plan 2.)

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/0018_sentinel_agent_identities.py
git commit -m "feat(audit): 0018 migration — agent_identities shell (Plan 2 populates)"
```

---

## Task 6: Migration 0019 — ingest_nodes (shell)

**Files:**
- Create: `api/alembic/versions/0019_sentinel_ingest_nodes.py`

> Shell for the `ingest_nodes` table so `audit_entries.ingest_node_id` has a valid FK. Full service implementation lands in Plan 2.

- [ ] **Step 1: Write the migration**

Create `api/alembic/versions/0019_sentinel_ingest_nodes.py`:

```python
"""sentinel ingest_nodes (shell — service lands in Plan 2)

Revision ID: 0019_sentinel_ingest_nodes
Revises: 0018_sentinel_agent_identities
Create Date: 2026-04-21 12:02:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision = "0019_sentinel_ingest_nodes"
down_revision = "0018_sentinel_agent_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingest_nodes",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("public_key", sa.LargeBinary, nullable=False),
        sa.Column("public_key_alg", sa.String(32), nullable=False),
        sa.Column("key_storage", sa.String(32), nullable=False),
        sa.Column("tpm_ak_quote", sa.LargeBinary, nullable=True),
        sa.Column(
            "operator_human_id",
            PgUUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "registration_audit_entry_id",
            sa.BigInteger,
            sa.ForeignKey("audit_entries.id"),
            nullable=False,
        ),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ingest_nodes")
```

- [ ] **Step 2: Re-run tests**

Run: `pytest api/tests/audit -v`
Expected: Existing tests still pass.

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/0019_sentinel_ingest_nodes.py
git commit -m "feat(audit): 0019 migration — ingest_nodes shell (Plan 2 populates)"
```

---

## Task 7: Migration 0020 — audit_entry_id cross-reference columns

**Files:**
- Create: `api/alembic/versions/0020_sentinel_audit_entry_refs.py`

> Adds nullable `audit_entry_id` FK columns on existing trajectory/node/heuristic tables. Nullable during migration; tightening happens in a later deployment-cycle migration after all rows have backfilled.

- [ ] **Step 1: Write the migration**

Create `api/alembic/versions/0020_sentinel_audit_entry_refs.py`:

```python
"""sentinel audit_entry_id cross-ref columns

Revision ID: 0020_sentinel_audit_entry_refs
Revises: 0019_sentinel_ingest_nodes
Create Date: 2026-04-21 12:03:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "0020_sentinel_audit_entry_refs"
down_revision = "0019_sentinel_ingest_nodes"
branch_labels = None
depends_on = None

_TABLES_WITH_AUDIT_REF = ["trajectories", "trajectory_nodes", "heuristic_hits"]


def upgrade() -> None:
    for table in _TABLES_WITH_AUDIT_REF:
        op.add_column(
            table,
            sa.Column(
                "audit_entry_id",
                sa.BigInteger,
                sa.ForeignKey("audit_entries.id"),
                nullable=True,
            ),
        )
        op.create_index(
            f"ix_{table}_audit_entry_id",
            table,
            ["audit_entry_id"],
        )


def downgrade() -> None:
    for table in _TABLES_WITH_AUDIT_REF:
        op.drop_index(f"ix_{table}_audit_entry_id", table_name=table)
        op.drop_column(table, "audit_entry_id")
```

- [ ] **Step 2: Run tests**

Run: `pytest api/tests -q`
Expected: All tests still pass; new column is nullable so existing fixtures are unaffected.

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/0020_sentinel_audit_entry_refs.py
git commit -m "feat(audit): 0020 migration — audit_entry_id FK columns on existing tables"
```

---

## Task 8: SQLAlchemy models for audit tables

**Files:**
- Create: `api/app/models/audit.py`
- Modify: `api/app/models/__init__.py` — export new models

- [ ] **Step 1: Write the failing test**

Create `api/tests/audit/test_models.py`:

```python
"""Smoke-tests for SQLAlchemy models — fields + relationships resolve."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models.audit import AuditEntry, AuditRoot, ExternalAnchor


@pytest.mark.asyncio
async def test_insert_and_query_audit_entry(session):
    entry = AuditEntry(
        seq=0,
        prev_hash=bytes(32),
        event_type="genesis",
        event_payload=b"{}",
        event_hash=bytes(32),
        entry_hash=bytes(32),
        ingest_node_id=uuid.uuid4(),
        ingest_signature=b"\x00" * 64,
        ts=datetime.now(timezone.utc),
    )
    session.add(entry)
    await session.flush()

    loaded = (await session.execute(select(AuditEntry).where(AuditEntry.seq == 0))).scalar_one()
    assert loaded.event_type == "genesis"
    assert loaded.entry_hash == bytes(32)


@pytest.mark.asyncio
async def test_audit_root_and_anchor_relationship(session):
    root = AuditRoot(
        tree_size=1,
        root_hash=bytes(32),
        computed_at=datetime.now(timezone.utc),
        ingest_node_id=uuid.uuid4(),
        ingest_signature=b"\x00" * 64,
    )
    session.add(root)
    await session.flush()

    anchor = ExternalAnchor(
        root_id=root.id,
        anchor_type="none",
        anchor_payload=b"",
        anchored_at=datetime.now(timezone.utc),
    )
    session.add(anchor)
    await session.flush()

    assert anchor.root_id == root.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.audit'`.

- [ ] **Step 3: Implement the models**

Create `api/app/models/audit.py`:

```python
"""SQLAlchemy models for audit-chain tables."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    seq: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    prev_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    event_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    entry_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    principal_human_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    agent_signature: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    ingest_node_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    ingest_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    agent_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_audit_entries_event_type_ts", "event_type", "ts"),
        Index("ix_audit_entries_agent_id_ts", "agent_id", "ts"),
        Index("ix_audit_entries_principal_human_id_ts", "principal_human_id", "ts"),
    )


class AuditRoot(Base):
    __tablename__ = "audit_roots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tree_size: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True)
    root_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingest_node_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    ingest_signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    anchors: Mapped[list["ExternalAnchor"]] = relationship(back_populates="root")


class ExternalAnchor(Base):
    __tablename__ = "external_anchors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    root_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("audit_roots.id"), nullable=False
    )
    anchor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    anchor_payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    anchored_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anchor_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    root: Mapped[AuditRoot] = relationship(back_populates="anchors")

    __table_args__ = (Index("ix_external_anchors_root_id", "root_id"),)
```

Modify `api/app/models/__init__.py` — add at the bottom (after existing exports):

```python
from app.models.audit import AuditEntry, AuditRoot, ExternalAnchor  # noqa: E402, F401
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_models.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/models/audit.py api/app/models/__init__.py api/tests/audit/test_models.py
git commit -m "feat(audit): SQLAlchemy models for audit_entries/roots/anchors"
```

---

## Task 9: AuditService.append — synchronous baseline (no batching)

**Files:**
- Create: `api/app/services/audit.py`
- Create: `api/tests/audit/test_audit_service.py`

> The baseline path proves the hash-chain computation is correct end-to-end against a real DB. Task 11 introduces the Writer singleton and batching on top of this interface.

- [ ] **Step 1: Write the failing test**

Create `api/tests/audit/test_audit_service.py`:

```python
"""AuditService append-path tests — chain continuity, signature presence."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models.audit import AuditEntry
from app.services.audit import AuditService


@pytest.fixture
def ingest_node():
    priv, pub = generate_keypair(SIG_ED25519)
    return {
        "node_id": uuid.uuid4(),
        "private_key": priv,
        "public_key": pub,
        "alg": SIG_ED25519,
    }


@pytest.mark.asyncio
async def test_append_first_entry_has_zero_prev_hash(session, ingest_node):
    svc = AuditService(session)
    entry = await svc.append(
        event_type="config.change",
        payload={"hello": "world"},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=ingest_node["node_id"],
        ingest_private_key=ingest_node["private_key"],
        ingest_alg=ingest_node["alg"],
    )
    assert entry.seq == 0
    assert entry.prev_hash == bytes(32)
    assert len(entry.entry_hash) == 32
    assert entry.entry_hash != bytes(32)


@pytest.mark.asyncio
async def test_append_chains_prev_hash(session, ingest_node):
    svc = AuditService(session)
    e1 = await svc.append(
        event_type="config.change",
        payload={"n": 1},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=ingest_node["node_id"],
        ingest_private_key=ingest_node["private_key"],
        ingest_alg=ingest_node["alg"],
    )
    e2 = await svc.append(
        event_type="config.change",
        payload={"n": 2},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=ingest_node["node_id"],
        ingest_private_key=ingest_node["private_key"],
        ingest_alg=ingest_node["alg"],
    )
    assert e1.seq == 0
    assert e2.seq == 1
    assert e2.prev_hash == e1.entry_hash


@pytest.mark.asyncio
async def test_append_signs_with_ingest_key(session, ingest_node):
    from app.audit.crypto import verify

    svc = AuditService(session)
    entry = await svc.append(
        event_type="config.change",
        payload={"x": 1},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=ingest_node["node_id"],
        ingest_private_key=ingest_node["private_key"],
        ingest_alg=ingest_node["alg"],
    )
    # ingest_signature signs (seq || prev_hash || event_hash || agent_signature-or-null)
    signed_buf = (
        entry.seq.to_bytes(8, "big")
        + entry.prev_hash
        + entry.event_hash
        + b"\x00"  # agent_signature is NULL → 0x00 sentinel
    )
    verify(ingest_node["public_key"], entry.ingest_signature, signed_buf, ingest_node["alg"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_audit_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.audit'`.

- [ ] **Step 3: Implement AuditService.append**

Create `api/app/services/audit.py`:

```python
"""AuditService — the single mutation entry point for the audit chain.

Every other service must call ``AuditService.append`` before persisting
its own rows. The baseline path here writes one entry per call; Task 11
layers the Writer singleton on top for batching under load.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.canonical import canonical_encode
from app.audit.crypto import sign
from app.audit.hashing import compute_entry_hash, sha256
from app.models.audit import AuditEntry


class AuditService:
    """Writes linked, signed entries into the audit chain."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        ingest_node_id: uuid.UUID,
        ingest_private_key: bytes,
        ingest_alg: str,
        agent_id: uuid.UUID | None = None,
        principal_human_id: uuid.UUID | None = None,
        agent_signature: bytes | None = None,
        agent_ts: datetime | None = None,
    ) -> AuditEntry:
        event_bytes = canonical_encode(payload)
        event_hash = sha256(event_bytes)

        prev = (
            await self._session.execute(
                select(AuditEntry.seq, AuditEntry.entry_hash).order_by(AuditEntry.seq.desc()).limit(1)
            )
        ).first()
        seq = 0 if prev is None else prev.seq + 1
        prev_hash = bytes(32) if prev is None else prev.entry_hash

        ts = datetime.now(timezone.utc)
        ts_iso = ts.isoformat().replace("+00:00", "Z")

        ingest_signed_buf = (
            seq.to_bytes(8, "big")
            + prev_hash
            + event_hash
            + (b"\x00" if agent_signature is None else b"\x01" + agent_signature)
        )
        ingest_signature = sign(ingest_private_key, ingest_signed_buf, ingest_alg)

        entry_hash = compute_entry_hash(
            seq=seq,
            prev_hash=prev_hash,
            event_hash=event_hash,
            agent_id=agent_id.bytes if agent_id else None,
            principal_human_id=principal_human_id.bytes if principal_human_id else None,
            ts_iso=ts_iso,
            agent_signature=agent_signature,
            ingest_signature=ingest_signature,
        )

        entry = AuditEntry(
            seq=seq,
            prev_hash=prev_hash,
            event_type=event_type,
            event_payload=event_bytes,
            event_hash=event_hash,
            entry_hash=entry_hash,
            agent_id=agent_id,
            principal_human_id=principal_human_id,
            agent_signature=agent_signature,
            ingest_node_id=ingest_node_id,
            ingest_signature=ingest_signature,
            ts=ts,
            agent_ts=agent_ts,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_audit_service.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/services/audit.py api/tests/audit/test_audit_service.py
git commit -m "feat(audit): AuditService.append — baseline chain-linking path"
```

---

## Task 10: Property test — chain continuity under many appends

**Files:**
- Create: `api/tests/audit/test_audit_chain_continuity.py`

- [ ] **Step 1: Write the property test**

Create `api/tests/audit/test_audit_chain_continuity.py`:

```python
"""Property test: chain continuity across many sequential appends."""
import uuid

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair
from app.audit.hashing import compute_entry_hash
from app.models.audit import AuditEntry
from app.services.audit import AuditService


@pytest.mark.asyncio
async def test_chain_continuity_and_entry_hash_recomputes(session):
    priv, _ = generate_keypair(SIG_ED25519)
    node_id = uuid.uuid4()
    svc = AuditService(session)

    N = 50
    for i in range(N):
        await svc.append(
            event_type="config.change",
            payload={"i": i},
            principal_human_id=uuid.uuid4(),
            ingest_node_id=node_id,
            ingest_private_key=priv,
            ingest_alg=SIG_ED25519,
        )

    rows = (await session.execute(select(AuditEntry).order_by(AuditEntry.seq))).scalars().all()
    assert len(rows) == N
    assert [r.seq for r in rows] == list(range(N))

    # prev_hash of each entry matches entry_hash of the previous
    for i in range(1, N):
        assert rows[i].prev_hash == rows[i - 1].entry_hash

    # entry_hash recomputes from the stored columns
    for r in rows:
        ts_iso = r.ts.isoformat().replace("+00:00", "Z")
        expected = compute_entry_hash(
            seq=r.seq,
            prev_hash=r.prev_hash,
            event_hash=r.event_hash,
            agent_id=r.agent_id.bytes if r.agent_id else None,
            principal_human_id=r.principal_human_id.bytes if r.principal_human_id else None,
            ts_iso=ts_iso,
            agent_signature=r.agent_signature,
            ingest_signature=r.ingest_signature,
        )
        assert r.entry_hash == expected, f"seq={r.seq}: entry_hash mismatch"
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_audit_chain_continuity.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add api/tests/audit/test_audit_chain_continuity.py
git commit -m "test(audit): property test — chain continuity across 50 appends"
```

---

## Task 11: Writer singleton with in-process batching

**Files:**
- Create: `api/app/audit/writer.py`
- Create: `api/tests/audit/test_writer.py`

> The Writer moves the chain-state cache into memory and batches submissions into one transaction per flush cycle. There is exactly one Writer per deployment (leader election in Task 12).

- [ ] **Step 1: Write the failing tests**

Create `api/tests/audit/test_writer.py`:

```python
"""Writer singleton tests — batching, order preservation, startup integrity."""
import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair
from app.audit.writer import AuditWriter, WriterIntegrityError
from app.models.audit import AuditEntry


@pytest.fixture
def node():
    priv, _ = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "alg": SIG_ED25519}


@pytest.mark.asyncio
async def test_writer_batches_and_preserves_submission_order(session_factory, node):
    writer = AuditWriter(
        session_factory=session_factory,
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
        batch_size=50,
        flush_interval_ms=10,
    )
    await writer.start()
    try:
        tasks = [
            writer.submit(event_type="config.change", payload={"i": i})
            for i in range(200)
        ]
        results = await asyncio.gather(*tasks)
    finally:
        await writer.stop()

    seqs = [r.seq for r in results]
    assert seqs == sorted(seqs), "submission order must produce monotonic seq"
    assert len(set(seqs)) == 200, "seqs must be unique"

    async with session_factory() as s:
        count = (await s.execute(select(AuditEntry))).scalars().all()
        assert len(count) == 200


@pytest.mark.asyncio
async def test_writer_startup_detects_corrupted_last_entry(session_factory, session, node):
    # Seed a row then corrupt its entry_hash.
    from app.services.audit import AuditService
    svc = AuditService(session)
    await svc.append(
        event_type="config.change",
        payload={"x": 1},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    await session.commit()

    async with session_factory() as s:
        row = (await s.execute(select(AuditEntry))).scalar_one()
        row.entry_hash = b"\xff" * 32
        await s.commit()

    writer = AuditWriter(
        session_factory=session_factory,
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    with pytest.raises(WriterIntegrityError, match="entry_hash"):
        await writer.start()
```

Add a `session_factory` fixture to `api/tests/conftest.py` (near the other engine fixtures) if one does not already exist:

```python
@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.writer'`.

- [ ] **Step 3: Implement the Writer**

Create `api/app/audit/writer.py`:

```python
"""Single-Writer audit submission queue.

The Writer owns the in-memory chain-state cache (``last_seq``,
``last_entry_hash``) and batches submissions into one transaction per
flush cycle. Exactly one Writer exists per deployment; leader election
is handled externally (Task 12).
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.canonical import canonical_encode
from app.audit.crypto import sign
from app.audit.hashing import compute_entry_hash, sha256
from app.models.audit import AuditEntry


class WriterIntegrityError(Exception):
    """Persisted chain state diverges from what the Writer can reconstruct."""


@dataclass
class _Submission:
    event_type: str
    payload: dict[str, Any]
    agent_id: uuid.UUID | None
    principal_human_id: uuid.UUID | None
    agent_signature: bytes | None
    agent_ts: datetime | None
    future: asyncio.Future


class AuditWriter:
    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
        ingest_node_id: uuid.UUID,
        ingest_private_key: bytes,
        ingest_alg: str,
        batch_size: int = 500,
        flush_interval_ms: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._node_id = ingest_node_id
        self._priv = ingest_private_key
        self._alg = ingest_alg
        self._batch_size = batch_size
        self._flush_interval_ms = flush_interval_ms

        self._queue: asyncio.Queue[_Submission] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._last_seq: int = -1
        self._last_entry_hash: bytes = bytes(32)

    async def start(self) -> None:
        await self._load_and_verify_chain_state()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def submit(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        agent_id: uuid.UUID | None = None,
        principal_human_id: uuid.UUID | None = None,
        agent_signature: bytes | None = None,
        agent_ts: datetime | None = None,
    ) -> AuditEntry:
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        await self._queue.put(
            _Submission(
                event_type=event_type,
                payload=payload,
                agent_id=agent_id,
                principal_human_id=principal_human_id,
                agent_signature=agent_signature,
                agent_ts=agent_ts,
                future=fut,
            )
        )
        return await fut

    async def _load_and_verify_chain_state(self) -> None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1)
                )
            ).scalar_one_or_none()
            if row is None:
                return
            ts_iso = row.ts.isoformat().replace("+00:00", "Z")
            expected = compute_entry_hash(
                seq=row.seq,
                prev_hash=row.prev_hash,
                event_hash=row.event_hash,
                agent_id=row.agent_id.bytes if row.agent_id else None,
                principal_human_id=row.principal_human_id.bytes
                if row.principal_human_id
                else None,
                ts_iso=ts_iso,
                agent_signature=row.agent_signature,
                ingest_signature=row.ingest_signature,
            )
            if expected != row.entry_hash:
                raise WriterIntegrityError(
                    f"entry_hash mismatch at seq={row.seq}: persisted value does not recompute"
                )
            self._last_seq = row.seq
            self._last_entry_hash = row.entry_hash

    async def _run(self) -> None:
        while True:
            batch: list[_Submission] = [await self._queue.get()]
            deadline = asyncio.get_event_loop().time() + self._flush_interval_ms / 1000
            while len(batch) < self._batch_size:
                timeout = deadline - asyncio.get_event_loop().time()
                if timeout <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self._queue.get(), timeout=timeout))
                except asyncio.TimeoutError:
                    break
            try:
                await self._flush(batch)
            except Exception as exc:  # noqa: BLE001
                for sub in batch:
                    if not sub.future.done():
                        sub.future.set_exception(exc)

    async def _flush(self, batch: list[_Submission]) -> None:
        async with self._session_factory() as session:
            rows: list[AuditEntry] = []
            for sub in batch:
                event_bytes = canonical_encode(sub.payload)
                event_hash = sha256(event_bytes)
                seq = self._last_seq + 1
                prev_hash = self._last_entry_hash
                ts = datetime.now(timezone.utc)
                ts_iso = ts.isoformat().replace("+00:00", "Z")

                ingest_signed_buf = (
                    seq.to_bytes(8, "big")
                    + prev_hash
                    + event_hash
                    + (b"\x00" if sub.agent_signature is None else b"\x01" + sub.agent_signature)
                )
                ingest_signature = sign(self._priv, ingest_signed_buf, self._alg)

                entry_hash = compute_entry_hash(
                    seq=seq,
                    prev_hash=prev_hash,
                    event_hash=event_hash,
                    agent_id=sub.agent_id.bytes if sub.agent_id else None,
                    principal_human_id=sub.principal_human_id.bytes
                    if sub.principal_human_id
                    else None,
                    ts_iso=ts_iso,
                    agent_signature=sub.agent_signature,
                    ingest_signature=ingest_signature,
                )

                row = AuditEntry(
                    seq=seq,
                    prev_hash=prev_hash,
                    event_type=sub.event_type,
                    event_payload=event_bytes,
                    event_hash=event_hash,
                    entry_hash=entry_hash,
                    agent_id=sub.agent_id,
                    principal_human_id=sub.principal_human_id,
                    agent_signature=sub.agent_signature,
                    ingest_node_id=self._node_id,
                    ingest_signature=ingest_signature,
                    ts=ts,
                    agent_ts=sub.agent_ts,
                )
                session.add(row)
                rows.append(row)
                self._last_seq = seq
                self._last_entry_hash = entry_hash
            await session.commit()
        for sub, row in zip(batch, rows, strict=True):
            if not sub.future.done():
                sub.future.set_result(row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_writer.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/audit/writer.py api/tests/audit/test_writer.py api/tests/conftest.py
git commit -m "feat(audit): Writer singleton with batching + startup integrity check"
```

---

## Task 12: Advisory-lock leader election

**Files:**
- Create: `api/app/audit/leader.py`
- Create: `api/tests/audit/test_leader.py`

> Guarantees at most one Writer is active at any time. Uses `pg_try_advisory_lock` on Postgres and falls back to an in-process lock on sqlite.

- [ ] **Step 1: Write the failing test**

Create `api/tests/audit/test_leader.py`:

```python
"""Writer leader-election tests."""
import asyncio

import pytest

from app.audit.leader import WRITER_LOCK_KEY, acquire_writer_lock


@pytest.mark.asyncio
async def test_acquire_writer_lock_is_exclusive(session_factory):
    async with session_factory() as s1, session_factory() as s2:
        got1 = await acquire_writer_lock(s1, WRITER_LOCK_KEY)
        got2 = await acquire_writer_lock(s2, WRITER_LOCK_KEY)
        assert got1 is True
        assert got2 is False


@pytest.mark.asyncio
async def test_writer_lock_released_on_session_close(session_factory):
    async with session_factory() as s1:
        got1 = await acquire_writer_lock(s1, WRITER_LOCK_KEY)
        assert got1 is True
    # Session closed; new session can acquire.
    async with session_factory() as s2:
        got2 = await acquire_writer_lock(s2, WRITER_LOCK_KEY)
        assert got2 is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_leader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.leader'`.

- [ ] **Step 3: Implement the lock helper**

Create `api/app/audit/leader.py`:

```python
"""Writer leader-election via Postgres session-scoped advisory locks.

Falls back to an in-process lock on sqlite (tests). The lock is held for
the lifetime of the session; closing the session releases the lock.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Arbitrary stable constant — advisory locks are keyed on this integer.
WRITER_LOCK_KEY = 0x73_65_6E_74_69  # "senti" ASCII

_sqlite_lock = asyncio.Lock()
_sqlite_held: set[int] = set()


async def acquire_writer_lock(session: AsyncSession, key: int) -> bool:
    dialect = session.bind.dialect.name if session.bind else ""
    if dialect == "postgresql":
        result = await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
        return bool(result.scalar())
    # sqlite fallback — process-local.
    async with _sqlite_lock:
        if key in _sqlite_held:
            return False
        _sqlite_held.add(key)

        # Tie release to session close via the session's `closed` lifecycle.
        original_close = session.close

        async def _release_and_close():
            _sqlite_held.discard(key)
            await original_close()

        session.close = _release_and_close  # type: ignore[method-assign]
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_leader.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/audit/leader.py api/tests/audit/test_leader.py
git commit -m "feat(audit): advisory-lock-based Writer leader election"
```

---

## Task 13: Merkle tree primitives (RFC 6962)

**Files:**
- Create: `api/app/audit/merkle.py`
- Create: `api/tests/audit/test_merkle.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/audit/test_merkle.py`:

```python
"""RFC 6962 Merkle tree tests — root, inclusion proof, consistency proof."""
import pytest

from app.audit.merkle import (
    merkle_root,
    inclusion_proof,
    verify_inclusion_proof,
    consistency_proof,
    verify_consistency_proof,
)
from app.audit.hashing import compute_leaf_hash, compute_internal_hash


def _leaves(n: int) -> list[bytes]:
    return [compute_leaf_hash(bytes([i]) * 32) for i in range(n)]


def test_single_leaf_root_is_the_leaf():
    leaves = _leaves(1)
    assert merkle_root(leaves) == leaves[0]


def test_two_leaf_root_is_hash_of_concat():
    leaves = _leaves(2)
    expected = compute_internal_hash(leaves[0], leaves[1])
    assert merkle_root(leaves) == expected


def test_three_leaf_tree_matches_rfc6962_left_heavy_split():
    # RFC 6962 §2.1: for N=3, split as [0,1] and [2].
    leaves = _leaves(3)
    left = compute_internal_hash(leaves[0], leaves[1])
    right = leaves[2]
    assert merkle_root(leaves) == compute_internal_hash(left, right)


@pytest.mark.parametrize("n", [1, 2, 3, 7, 8, 15, 16, 100])
def test_inclusion_proof_roundtrip_for_every_leaf(n):
    leaves = _leaves(n)
    root = merkle_root(leaves)
    for idx in range(n):
        proof = inclusion_proof(leaves, idx)
        assert verify_inclusion_proof(
            leaf_hash=leaves[idx], index=idx, tree_size=n, proof=proof, root=root
        ) is True


def test_inclusion_proof_detects_tamper():
    leaves = _leaves(8)
    root = merkle_root(leaves)
    proof = inclusion_proof(leaves, 3)
    tampered = bytes([b ^ 0xFF for b in leaves[3]])
    assert verify_inclusion_proof(
        leaf_hash=tampered, index=3, tree_size=8, proof=proof, root=root
    ) is False


@pytest.mark.parametrize("n1,n2", [(1, 2), (1, 8), (5, 8), (7, 8), (8, 16)])
def test_consistency_proof_roundtrip(n1, n2):
    leaves = _leaves(n2)
    root1 = merkle_root(leaves[:n1])
    root2 = merkle_root(leaves)
    proof = consistency_proof(leaves, n1)
    assert verify_consistency_proof(
        old_size=n1, new_size=n2, old_root=root1, new_root=root2, proof=proof
    ) is True


def test_consistency_proof_detects_different_prefix():
    leaves_a = _leaves(8)
    leaves_b = [compute_leaf_hash(bytes([i + 1]) * 32) for i in range(8)]
    root_a1 = merkle_root(leaves_a[:4])
    root_b2 = merkle_root(leaves_b)
    proof = consistency_proof(leaves_b, 4)
    assert verify_consistency_proof(
        old_size=4, new_size=8, old_root=root_a1, new_root=root_b2, proof=proof
    ) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_merkle.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.merkle'`.

- [ ] **Step 3: Implement the Merkle primitives**

Create `api/app/audit/merkle.py`:

```python
"""RFC 6962 Merkle tree and proof primitives.

Implements the left-heavy split, inclusion proofs, and consistency
proofs from RFC 6962. Verification helpers do not trust inputs — they
recompute the root from the claimed leaf and proof.
"""
from __future__ import annotations

from app.audit.hashing import compute_internal_hash


def _largest_power_of_two_less_than(n: int) -> int:
    """Largest k such that 2**k < n, for n > 1."""
    k = 1
    while k * 2 < n:
        k *= 2
    return k


def merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        raise ValueError("merkle_root requires at least one leaf")
    if len(leaves) == 1:
        return leaves[0]
    k = _largest_power_of_two_less_than(len(leaves))
    left = merkle_root(leaves[:k])
    right = merkle_root(leaves[k:])
    return compute_internal_hash(left, right)


def inclusion_proof(leaves: list[bytes], index: int) -> list[bytes]:
    if not 0 <= index < len(leaves):
        raise ValueError("index out of range")
    return _inclusion_proof_recursive(leaves, index)


def _inclusion_proof_recursive(leaves: list[bytes], index: int) -> list[bytes]:
    n = len(leaves)
    if n == 1:
        return []
    k = _largest_power_of_two_less_than(n)
    if index < k:
        return _inclusion_proof_recursive(leaves[:k], index) + [merkle_root(leaves[k:])]
    return _inclusion_proof_recursive(leaves[k:], index - k) + [merkle_root(leaves[:k])]


def verify_inclusion_proof(
    *,
    leaf_hash: bytes,
    index: int,
    tree_size: int,
    proof: list[bytes],
    root: bytes,
) -> bool:
    if not 0 <= index < tree_size:
        return False
    computed = leaf_hash
    node_idx = index
    last_node = tree_size - 1
    for sibling in proof:
        if node_idx == last_node and node_idx % 2 == 0:
            # Right-edge orphan — carry up without hashing.
            node_idx //= 2
            last_node //= 2
            continue
        if node_idx % 2 == 0:
            computed = compute_internal_hash(computed, sibling)
        else:
            computed = compute_internal_hash(sibling, computed)
        node_idx //= 2
        last_node //= 2
    return computed == root


def consistency_proof(leaves: list[bytes], old_size: int) -> list[bytes]:
    if not 0 < old_size <= len(leaves):
        raise ValueError("invalid old_size")
    if old_size == len(leaves):
        return []
    return _consistency_proof_recursive(leaves, old_size, True)


def _consistency_proof_recursive(leaves: list[bytes], m: int, b: bool) -> list[bytes]:
    n = len(leaves)
    if m == n:
        return [] if b else [merkle_root(leaves)]
    k = _largest_power_of_two_less_than(n)
    if m <= k:
        return _consistency_proof_recursive(leaves[:k], m, b) + [merkle_root(leaves[k:])]
    return _consistency_proof_recursive(leaves[k:], m - k, False) + [merkle_root(leaves[:k])]


def verify_consistency_proof(
    *,
    old_size: int,
    new_size: int,
    old_root: bytes,
    new_root: bytes,
    proof: list[bytes],
) -> bool:
    if old_size == 0 or old_size > new_size:
        return False
    if old_size == new_size:
        return not proof and old_root == new_root
    # Per RFC 6962 §2.1.2.
    if old_size == 1 << (old_size.bit_length() - 1) and old_size.bit_length() - 1 > 0 and (
        old_size & (old_size - 1)
    ) == 0:
        # old_size is a power of two with old_size < new_size
        pass
    # Simplified verifier: rebuild both roots from the proof using the
    # classic CT algorithm.
    # Reference: RFC 6962 §2.1.2 verification pseudocode.
    node = old_size - 1
    last_node = new_size - 1
    while node % 2 == 1:
        node //= 2
        last_node //= 2
    fn_hash = sn_hash = None
    if node == 0:
        fn_hash = sn_hash = old_root
    else:
        if not proof:
            return False
        fn_hash = sn_hash = proof[0]
        proof = proof[1:]
    for p in proof:
        if last_node == 0:
            return False
        if node % 2 == 1 or node == last_node:
            fn_hash = compute_internal_hash(p, fn_hash)
            sn_hash = compute_internal_hash(p, sn_hash)
            while node % 2 == 0 and node != 0:
                node //= 2
                last_node //= 2
        else:
            sn_hash = compute_internal_hash(sn_hash, p)
        node //= 2
        last_node //= 2
    return fn_hash == old_root and sn_hash == new_root and last_node == 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_merkle.py -v`
Expected: 14 passed (parametrized counts: 8 inclusion + 5 consistency + 3 singletons).

- [ ] **Step 5: Commit**

```bash
git add api/app/audit/merkle.py api/tests/audit/test_merkle.py
git commit -m "feat(audit): RFC 6962 Merkle tree + inclusion/consistency proofs"
```

---

## Task 14: Root snapshotting in AuditService

**Files:**
- Modify: `api/app/services/audit.py` — add `snapshot_root` + `get_inclusion_proof` + `get_consistency_proof` + `recent_root`
- Create: `api/tests/audit/test_audit_roots.py`

- [ ] **Step 1: Write the failing tests**

Create `api/tests/audit/test_audit_roots.py`:

```python
"""Root snapshotting + proof retrieval tests."""
import uuid

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair, verify
from app.audit.hashing import compute_leaf_hash
from app.audit.merkle import merkle_root, verify_inclusion_proof
from app.models.audit import AuditEntry, AuditRoot
from app.services.audit import AuditService


@pytest.fixture
def node():
    priv, pub = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "pub": pub, "alg": SIG_ED25519}


async def _append_n(session, svc, node, n):
    for i in range(n):
        await svc.append(
            event_type="config.change",
            payload={"i": i},
            principal_human_id=uuid.uuid4(),
            ingest_node_id=node["node_id"],
            ingest_private_key=node["priv"],
            ingest_alg=node["alg"],
        )


@pytest.mark.asyncio
async def test_snapshot_root_computes_merkle_over_all_entries(session, node):
    svc = AuditService(session)
    await _append_n(session, svc, node, 10)
    root = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )

    entries = (
        await session.execute(select(AuditEntry).order_by(AuditEntry.seq))
    ).scalars().all()
    leaves = [compute_leaf_hash(e.entry_hash) for e in entries]
    expected = merkle_root(leaves)
    assert root.tree_size == 10
    assert root.root_hash == expected


@pytest.mark.asyncio
async def test_snapshot_root_signature_verifies(session, node):
    svc = AuditService(session)
    await _append_n(session, svc, node, 3)
    root = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    signed = root.tree_size.to_bytes(8, "big") + root.root_hash
    verify(node["pub"], root.ingest_signature, signed, node["alg"])


@pytest.mark.asyncio
async def test_inclusion_proof_verifies_against_snapshot(session, node):
    svc = AuditService(session)
    await _append_n(session, svc, node, 20)
    root = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    entry = (
        await session.execute(select(AuditEntry).where(AuditEntry.seq == 7))
    ).scalar_one()
    proof = await svc.get_inclusion_proof(seq=7, tree_size=20)
    assert verify_inclusion_proof(
        leaf_hash=compute_leaf_hash(entry.entry_hash),
        index=7,
        tree_size=20,
        proof=proof,
        root=root.root_hash,
    )


@pytest.mark.asyncio
async def test_recent_root_returns_latest(session, node):
    svc = AuditService(session)
    await _append_n(session, svc, node, 5)
    r1 = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    await _append_n(session, svc, node, 3)
    r2 = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    latest = await svc.recent_root()
    assert latest.id == r2.id
    assert latest.id != r1.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_audit_roots.py -v`
Expected: FAIL — `AttributeError: 'AuditService' object has no attribute 'snapshot_root'`.

- [ ] **Step 3: Extend AuditService**

Append to `api/app/services/audit.py`:

```python
from app.audit.hashing import compute_leaf_hash
from app.audit.merkle import (
    consistency_proof as _consistency_proof,
    inclusion_proof as _inclusion_proof,
    merkle_root,
)
from app.models.audit import AuditRoot


class _AuditServiceExtensions:
    """Mixed into AuditService below via monkey-methods — keeps file order tidy."""


async def _load_entry_hashes_up_to(session, tree_size: int) -> list[bytes]:
    result = await session.execute(
        select(AuditEntry.entry_hash)
        .where(AuditEntry.seq < tree_size)
        .order_by(AuditEntry.seq)
    )
    return [row[0] for row in result.all()]


async def snapshot_root(
    self,
    *,
    ingest_node_id: uuid.UUID,
    ingest_private_key: bytes,
    ingest_alg: str,
) -> AuditRoot:
    entry_hashes = (
        await self._session.execute(
            select(AuditEntry.entry_hash).order_by(AuditEntry.seq)
        )
    ).scalars().all()
    tree_size = len(entry_hashes)
    if tree_size == 0:
        raise ValueError("cannot snapshot root of empty log")
    leaves = [compute_leaf_hash(h) for h in entry_hashes]
    root_hash = merkle_root(leaves)
    signed = tree_size.to_bytes(8, "big") + root_hash
    sig = sign(ingest_private_key, signed, ingest_alg)
    root = AuditRoot(
        tree_size=tree_size,
        root_hash=root_hash,
        computed_at=datetime.now(timezone.utc),
        ingest_node_id=ingest_node_id,
        ingest_signature=sig,
    )
    self._session.add(root)
    await self._session.flush()
    return root


async def get_inclusion_proof(self, *, seq: int, tree_size: int) -> list[bytes]:
    hashes = await _load_entry_hashes_up_to(self._session, tree_size)
    leaves = [compute_leaf_hash(h) for h in hashes]
    return _inclusion_proof(leaves, seq)


async def get_consistency_proof(self, *, old_size: int, new_size: int) -> list[bytes]:
    hashes = await _load_entry_hashes_up_to(self._session, new_size)
    leaves = [compute_leaf_hash(h) for h in hashes]
    return _consistency_proof(leaves, old_size)


async def recent_root(self) -> AuditRoot | None:
    return (
        await self._session.execute(
            select(AuditRoot).order_by(AuditRoot.tree_size.desc()).limit(1)
        )
    ).scalar_one_or_none()


AuditService.snapshot_root = snapshot_root
AuditService.get_inclusion_proof = get_inclusion_proof
AuditService.get_consistency_proof = get_consistency_proof
AuditService.recent_root = recent_root
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_audit_roots.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/services/audit.py api/tests/audit/test_audit_roots.py
git commit -m "feat(audit): root snapshotting + inclusion/consistency proof retrieval"
```

---

## Task 15: External anchor abstract interface + "none" anchor

**Files:**
- Create: `api/app/audit/anchor/__init__.py`
- Create: `api/app/audit/anchor/base.py`
- Create: `api/app/audit/anchor/none_anchor.py`
- Create: `api/tests/audit/test_anchor_base.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/audit/test_anchor_base.py`:

```python
"""Anchor interface tests — 'none' anchor writes an ExternalAnchor row."""
import uuid

import pytest
from sqlalchemy import select

from app.audit.anchor.none_anchor import NoneAnchor
from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models.audit import ExternalAnchor
from app.services.audit import AuditService


@pytest.fixture
def node():
    priv, _ = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "alg": SIG_ED25519}


@pytest.mark.asyncio
async def test_none_anchor_writes_anchor_row(session, node):
    svc = AuditService(session)
    await svc.append(
        event_type="config.change",
        payload={"x": 1},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    root = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )

    anchor = NoneAnchor()
    created = await anchor.anchor(session, root)

    rows = (await session.execute(select(ExternalAnchor))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == created.id
    assert rows[0].anchor_type == "none"
    assert rows[0].root_id == root.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_anchor_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.anchor'`.

- [ ] **Step 3: Implement anchor interface + none anchor**

Create `api/app/audit/anchor/__init__.py` (empty).

Create `api/app/audit/anchor/base.py`:

```python
"""Abstract external-anchor interface.

A deployment may configure zero-or-more anchor types. Each ``anchor``
call persists one ``ExternalAnchor`` row bound to the given
``AuditRoot``. Anchor implementations never mutate other tables.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditRoot, ExternalAnchor


class ExternalAnchorBackend(ABC):
    """Base class for anchor backends."""

    #: Matches ``ExternalAnchor.anchor_type``. One value per subclass.
    anchor_type: str

    @abstractmethod
    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        """Produce and persist an ExternalAnchor row for ``root``."""
        raise NotImplementedError
```

Create `api/app/audit/anchor/none_anchor.py`:

```python
"""Dev-only no-op anchor. Production profiles reject this at startup."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.anchor.base import ExternalAnchorBackend
from app.models.audit import AuditRoot, ExternalAnchor


class NoneAnchor(ExternalAnchorBackend):
    anchor_type = "none"

    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        row = ExternalAnchor(
            root_id=root.id,
            anchor_type=self.anchor_type,
            anchor_payload=b"",
            anchored_at=datetime.now(timezone.utc),
            anchor_ref=None,
        )
        session.add(row)
        await session.flush()
        return row
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_anchor_base.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/audit/anchor/__init__.py api/app/audit/anchor/base.py api/app/audit/anchor/none_anchor.py api/tests/audit/test_anchor_base.py
git commit -m "feat(audit): ExternalAnchor interface + none (dev) anchor"
```

---

## Task 16: Offline file-signer anchor

**Files:**
- Create: `api/app/audit/anchor/offline_file.py`
- Create: `api/tests/audit/test_anchor_offline_file.py`

> The offline-file anchor writes a root-attestation bundle to a directory, shells out to a customer-configured signer command, reads the signed result, and persists it as the anchor payload. For air-gap deployments.

- [ ] **Step 1: Write the failing test**

Create `api/tests/audit/test_anchor_offline_file.py`:

```python
"""Offline-file anchor test — signer command is invoked, output persisted."""
import shutil
import stat
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.audit.anchor.offline_file import OfflineFileAnchor
from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models.audit import ExternalAnchor
from app.services.audit import AuditService


@pytest.fixture
def node():
    priv, _ = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "alg": SIG_ED25519}


@pytest.mark.asyncio
async def test_offline_file_anchor_runs_signer(tmp_path: Path, session, node):
    # Stub signer: concatenates the root-hash file with a fixed "SIGNED-" prefix.
    signer = tmp_path / "signer.sh"
    signer.write_text(
        "#!/bin/sh\n"
        "IN=$1\n"
        "OUT=$2\n"
        "printf 'SIGNED-' > $OUT && cat $IN >> $OUT\n"
    )
    signer.chmod(signer.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    svc = AuditService(session)
    await svc.append(
        event_type="config.change",
        payload={"x": 1},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    root = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )

    anchor = OfflineFileAnchor(
        signer_command=str(signer),
        work_dir=tmp_path / "work",
        anchor_ref="test-signer",
    )
    created = await anchor.anchor(session, root)

    rows = (await session.execute(select(ExternalAnchor))).scalars().all()
    assert len(rows) == 1
    # Signer output = "SIGNED-" + root-file bytes (tree_size||root_hash).
    expected = b"SIGNED-" + root.tree_size.to_bytes(8, "big") + root.root_hash
    assert rows[0].anchor_payload == expected
    assert rows[0].anchor_ref == "test-signer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_anchor_offline_file.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.anchor.offline_file'`.

- [ ] **Step 3: Implement the offline-file anchor**

Create `api/app/audit/anchor/offline_file.py`:

```python
"""Offline file-signer external anchor.

Invokes a customer-configured signer command with two arguments:
an input file containing ``tree_size||root_hash`` and an output file
where the signer writes its signed attestation. Used in air-gap
deployments where the signer is a smartcard- or PIV-backed process.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.anchor.base import ExternalAnchorBackend
from app.models.audit import AuditRoot, ExternalAnchor


class OfflineFileAnchor(ExternalAnchorBackend):
    anchor_type = "offline_file"

    def __init__(
        self,
        *,
        signer_command: str,
        work_dir: Path | str,
        anchor_ref: str | None = None,
    ) -> None:
        self._signer = signer_command
        self._work_dir = Path(work_dir)
        self._anchor_ref = anchor_ref

    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        self._work_dir.mkdir(parents=True, exist_ok=True)
        in_path = self._work_dir / f"root-{root.tree_size}.bin"
        out_path = self._work_dir / f"root-{root.tree_size}.signed"
        in_path.write_bytes(root.tree_size.to_bytes(8, "big") + root.root_hash)

        proc = await asyncio.create_subprocess_exec(
            self._signer, str(in_path), str(out_path)
        )
        rc = await proc.wait()
        if rc != 0:
            raise RuntimeError(f"signer_command exited with {rc}")
        payload = out_path.read_bytes()

        row = ExternalAnchor(
            root_id=root.id,
            anchor_type=self.anchor_type,
            anchor_payload=payload,
            anchored_at=datetime.now(timezone.utc),
            anchor_ref=self._anchor_ref,
        )
        session.add(row)
        await session.flush()
        return row
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest api/tests/audit/test_anchor_offline_file.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/app/audit/anchor/offline_file.py api/tests/audit/test_anchor_offline_file.py
git commit -m "feat(audit): offline file-signer external anchor for air-gap"
```

---

## Task 17: RFC 3161 TSA anchor

**Files:**
- Create: `api/app/audit/anchor/rfc3161.py`
- Create: `api/tests/audit/test_anchor_rfc3161.py`
- Modify: `api/pyproject.toml` — add `asn1crypto>=1.5,<2.0`

> Implements the RFC 3161 Time-Stamp Protocol request/response cycle. Test uses a fake-TSA HTTP mock — real TSA interop is exercised in integration tests.

- [ ] **Step 1: Add the dependency**

Modify `api/pyproject.toml`:

```toml
"asn1crypto>=1.5,<2.0",
"httpx>=0.27,<0.28",  # already present, confirm
```

Run: `cd api && uv pip install -e .`

- [ ] **Step 2: Write the failing test**

Create `api/tests/audit/test_anchor_rfc3161.py`:

```python
"""RFC 3161 TSA anchor test — a fake TSA echoes a fixed TimeStampToken blob."""
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select

from app.audit.anchor.rfc3161 import RFC3161Anchor
from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models.audit import ExternalAnchor
from app.services.audit import AuditService


@pytest.fixture
def node():
    priv, _ = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "alg": SIG_ED25519}


@pytest.mark.asyncio
async def test_rfc3161_anchor_posts_request_and_stores_response(session, node):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Content-Type"] == "application/timestamp-query"
        # We don't validate the TimeStampReq bytes here — interop is tested
        # against a real TSA. We just prove the anchor POSTs to the URL and
        # persists the response body.
        return httpx.Response(200, content=b"FAKE-TSR-BLOB")

    transport = httpx.MockTransport(handler)

    svc = AuditService(session)
    await svc.append(
        event_type="config.change",
        payload={"x": 1},
        principal_human_id=uuid.uuid4(),
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    root = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )

    anchor = RFC3161Anchor(
        tsa_url="https://tsa.example/req",
        anchor_ref="tsa.example",
        http_client=httpx.AsyncClient(transport=transport),
    )
    created = await anchor.anchor(session, root)

    rows = (await session.execute(select(ExternalAnchor))).scalars().all()
    assert len(rows) == 1
    assert rows[0].anchor_type == "rfc3161_tsa"
    assert rows[0].anchor_payload == b"FAKE-TSR-BLOB"
    assert rows[0].anchor_ref == "tsa.example"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest api/tests/audit/test_anchor_rfc3161.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.audit.anchor.rfc3161'`.

- [ ] **Step 4: Implement the RFC 3161 anchor**

Create `api/app/audit/anchor/rfc3161.py`:

```python
"""RFC 3161 Time-Stamp Protocol anchor.

Builds a TimeStampReq (ASN.1 DER) containing the root hash, POSTs to the
configured TSA URL with ``Content-Type: application/timestamp-query``,
and stores the response body (TimeStampResp) as the anchor payload.
Interop with a real TSA is exercised in separate integration tests.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

import httpx
from asn1crypto import tsp
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.anchor.base import ExternalAnchorBackend
from app.models.audit import AuditRoot, ExternalAnchor


class RFC3161Anchor(ExternalAnchorBackend):
    anchor_type = "rfc3161_tsa"

    def __init__(
        self,
        *,
        tsa_url: str,
        anchor_ref: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = tsa_url
        self._anchor_ref = anchor_ref
        self._http = http_client or httpx.AsyncClient()

    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        req = tsp.TimeStampReq(
            {
                "version": "v1",
                "message_imprint": {
                    "hash_algorithm": {"algorithm": "sha256"},
                    "hashed_message": root.root_hash,
                },
                "nonce": int.from_bytes(secrets.token_bytes(8), "big"),
                "cert_req": True,
            }
        )
        resp = await self._http.post(
            self._url,
            content=req.dump(),
            headers={"Content-Type": "application/timestamp-query"},
        )
        resp.raise_for_status()

        row = ExternalAnchor(
            root_id=root.id,
            anchor_type=self.anchor_type,
            anchor_payload=resp.content,
            anchored_at=datetime.now(timezone.utc),
            anchor_ref=self._anchor_ref,
        )
        session.add(row)
        await session.flush()
        return row
```

- [ ] **Step 5: Run tests to verify they pass, then commit**

Run: `pytest api/tests/audit/test_anchor_rfc3161.py -v`
Expected: 1 passed.

```bash
git add api/pyproject.toml api/app/audit/anchor/rfc3161.py api/tests/audit/test_anchor_rfc3161.py
git commit -m "feat(audit): RFC 3161 TSA external anchor"
```

---

## Task 18: End-to-end — Writer → append → snapshot → anchor → verify

**Files:**
- Create: `api/tests/audit/test_audit_e2e.py`

- [ ] **Step 1: Write the end-to-end test**

Create `api/tests/audit/test_audit_e2e.py`:

```python
"""End-to-end: Writer appends many events, snapshot a root, anchor it,
verify inclusion proofs for a sampled entry."""
import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.audit.anchor.none_anchor import NoneAnchor
from app.audit.crypto import SIG_ED25519, generate_keypair, verify
from app.audit.hashing import compute_leaf_hash
from app.audit.merkle import verify_inclusion_proof
from app.audit.writer import AuditWriter
from app.models.audit import AuditEntry, AuditRoot, ExternalAnchor
from app.services.audit import AuditService


@pytest.mark.asyncio
async def test_end_to_end_writer_append_snapshot_anchor_verify(session_factory):
    priv, pub = generate_keypair(SIG_ED25519)
    node_id = uuid.uuid4()

    writer = AuditWriter(
        session_factory=session_factory,
        ingest_node_id=node_id,
        ingest_private_key=priv,
        ingest_alg=SIG_ED25519,
        batch_size=50,
        flush_interval_ms=5,
    )
    await writer.start()
    try:
        N = 100
        results = await asyncio.gather(
            *[
                writer.submit(event_type="config.change", payload={"i": i})
                for i in range(N)
            ]
        )
    finally:
        await writer.stop()

    assert [r.seq for r in results] == list(range(N))

    # Snapshot a root and anchor with the no-op (dev) anchor.
    async with session_factory() as session:
        svc = AuditService(session)
        root = await svc.snapshot_root(
            ingest_node_id=node_id,
            ingest_private_key=priv,
            ingest_alg=SIG_ED25519,
        )
        anchor = NoneAnchor()
        anchor_row = await anchor.anchor(session, root)
        await session.commit()

    assert root.tree_size == N

    # Verify the snapshot signature.
    verify(pub, root.ingest_signature, root.tree_size.to_bytes(8, "big") + root.root_hash, SIG_ED25519)

    # Pick a few sample indices, fetch inclusion proofs, verify against the root.
    async with session_factory() as session:
        svc = AuditService(session)
        for idx in (0, 1, 42, 99):
            entry = (
                await session.execute(select(AuditEntry).where(AuditEntry.seq == idx))
            ).scalar_one()
            proof = await svc.get_inclusion_proof(seq=idx, tree_size=N)
            assert verify_inclusion_proof(
                leaf_hash=compute_leaf_hash(entry.entry_hash),
                index=idx,
                tree_size=N,
                proof=proof,
                root=root.root_hash,
            ), f"inclusion proof failed at seq={idx}"

    # Anchor row persists.
    async with session_factory() as session:
        rows = (await session.execute(select(ExternalAnchor))).scalars().all()
        assert len(rows) == 1
        assert rows[0].anchor_type == "none"
```

- [ ] **Step 2: Run the test**

Run: `pytest api/tests/audit/test_audit_e2e.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add api/tests/audit/test_audit_e2e.py
git commit -m "test(audit): end-to-end — Writer append → snapshot → anchor → verify"
```

---

## Task 19: Full test-suite run + lint

**Files:**
- None (verification only)

- [ ] **Step 1: Run the full audit test suite**

Run: `pytest api/tests/audit -v`
Expected: all tests pass (approximately 30+).

- [ ] **Step 2: Run the full api test suite**

Run: `cd api && pytest -q`
Expected: all pre-existing tests still pass; new audit tests pass.

- [ ] **Step 3: Run ruff**

Run: `ruff check api/`
Expected: clean, or only pre-existing warnings.

- [ ] **Step 4: Run ruff on new files only if lint noise bleeds in**

Run: `ruff check api/app/audit api/app/models/audit.py api/app/services/audit.py api/tests/audit`
Expected: clean.

- [ ] **Step 5: Commit any lint fixes if needed**

```bash
git add -A
git commit -m "chore(audit): ruff fixes" --allow-empty
```

(`--allow-empty` in case nothing needed fixing; the commit is skipped with exit 0.)

---

## Self-Review

### Spec coverage

Mapping every item from the child spec to a task:

| Spec section | Plan coverage |
|---|---|
| JCS canonical encoding | Task 1 |
| Ed25519 + ECDSA P-384 signing | Task 2 |
| Entry hash, leaf hash, internal hash | Task 3 |
| `audit_entries` + append-only trigger | Task 4 |
| `audit_roots`, `external_anchors` | Task 4 |
| `agent_identities` (shell) | Task 5 |
| `ingest_nodes` (shell) | Task 6 |
| `audit_entry_id` FK cross-ref | Task 7 |
| SQLAlchemy models for audit tables | Task 8 |
| `AuditService.append` | Tasks 9, 10 |
| Writer singleton with batching | Task 11 |
| Writer startup integrity check | Task 11 |
| Advisory-lock leader election | Task 12 |
| Merkle tree RFC 6962 + proofs | Task 13 |
| Root snapshotting + proof retrieval | Task 14 |
| Anchor abstract interface + none | Task 15 |
| Offline-file anchor | Task 16 |
| RFC 3161 TSA anchor | Task 17 |
| End-to-end verification | Task 18 |
| Full test + lint run | Task 19 |

**Spec items deferred to later plans (called out in this plan's Scope):**

- Agent identity issuance flow + bootstrap tokens (Plan 2).
- Ingest-node key generation + TPM quote verification (Plan 2).
- OTLP ingest endpoint wiring (Plan 2).
- SDK `KeyStore` + per-span signing + bootstrap CLI (Plan 2).
- `sentinel-verify` offline verifier CLI (Plan 3, separate repo).
- Internal PKI anchor — interface is open; implementation deferred until a customer requires it.
- Rate-limited `span.reject` path — deferred to Plan 2 where it lives alongside ingest wiring.
- Root-snapshot scheduler — deferred; `snapshot_root` is called explicitly in Plan 1. A scheduler daemon is a Plan 2 concern because it couples to ingest lifecycle.

### Placeholder scan

- No "TBD" / "TODO" in task bodies.
- No "implement appropriate error handling" without code.
- No "similar to Task N" — code is repeated where needed for standalone readability.
- No undefined types or functions referenced across tasks.

### Type / signature consistency

- `AuditService.append` signature is identical in Task 9 (definition), Task 10 (property test), Task 14 (extension), Task 15 (anchor test), Task 17 (RFC 3161 test), and Task 18 (E2E).
- `AuditWriter.submit` signature is identical in Task 11 (definition) and Task 18 (E2E).
- `compute_entry_hash` keyword arguments are identical in Task 3 (definition), Task 9 (service use), Task 10 (recompute in test), Task 11 (Writer use).
- `inclusion_proof` / `verify_inclusion_proof` signatures identical across Task 13 (definition), Task 14 (service use), Task 18 (E2E).
- `ExternalAnchorBackend.anchor` signature identical in Task 15, 16, 17.

### Scope

This plan stops at audit-chain core end-to-end verification. Plans 2 and 3 sequence on top. No scope creep into agent identity, ingest wiring, SDK, or the verifier CLI.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-21-sentinel-audit-chain-core.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
