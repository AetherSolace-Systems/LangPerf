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
        ("agent_id", b"\xfe" * 16),
        ("principal_human_id", b"\xfe" * 16),
        ("ts_iso", "2026-04-22T00:00:00Z"),
        ("agent_signature", b"\xfe" * 64),
        ("ingest_signature", b"\x00" * 64),
    ]:
        mutated = {**base, field: new_value}
        assert compute_entry_hash(**mutated) != h_base, f"{field} should affect entry_hash"


def test_compute_entry_hash_distinguishes_none_from_bytes():
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
    h_all_none = compute_entry_hash(**base)
    for field, some_value in [
        ("agent_id", b"\x00" * 16),
        ("principal_human_id", b"\x00" * 16),
        ("agent_signature", b"\x00" * 64),
    ]:
        mutated = {**base, field: some_value}
        assert compute_entry_hash(**mutated) != h_all_none, (
            f"None vs bytes transition on {field} must change entry_hash"
        )
