"""Root snapshotting + proof retrieval tests."""
import uuid

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair, verify
from app.audit.hashing import compute_leaf_hash
from app.audit.merkle import merkle_root, verify_inclusion_proof
from app.models import AuditEntry
from app.services.audit import AuditService


@pytest.fixture
def node():
    priv, pub = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "pub": pub, "alg": SIG_ED25519}


async def _append_n(svc, node, n):
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
    await _append_n(svc, node, 10)
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
    await _append_n(svc, node, 3)
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
    await _append_n(svc, node, 20)
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
    await _append_n(svc, node, 5)
    r1 = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    await _append_n(svc, node, 3)
    r2 = await svc.snapshot_root(
        ingest_node_id=node["node_id"],
        ingest_private_key=node["priv"],
        ingest_alg=node["alg"],
    )
    latest = await svc.recent_root()
    assert latest.id == r2.id
    assert latest.id != r1.id
