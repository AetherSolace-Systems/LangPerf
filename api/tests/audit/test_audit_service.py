"""AuditService append-path tests — chain continuity, signature verification."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models import AuditEntry
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
    signed_buf = (
        entry.seq.to_bytes(8, "big")
        + entry.prev_hash
        + entry.event_hash
        + b"\x00"  # agent_signature is NULL → 0x00 sentinel
    )
    verify(ingest_node["public_key"], entry.ingest_signature, signed_buf, ingest_node["alg"])
