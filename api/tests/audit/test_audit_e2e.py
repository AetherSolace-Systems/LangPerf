"""End-to-end: Writer appends many events, snapshot a root, anchor it,
verify inclusion proofs for sampled entries."""
import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.audit.anchor.none_anchor import NoneAnchor
from app.audit.crypto import SIG_ED25519, generate_keypair, verify
from app.audit.hashing import compute_leaf_hash
from app.audit.merkle import verify_inclusion_proof
from app.audit.writer import AuditWriter
from app.models import AuditEntry, ExternalAnchor
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
        await anchor.anchor(session, root)
        await session.commit()

    assert root.tree_size == N

    # Verify the snapshot signature.
    verify(
        pub,
        root.ingest_signature,
        root.tree_size.to_bytes(8, "big") + root.root_hash,
        SIG_ED25519,
    )

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
