"""Writer singleton tests — batching, order preservation, startup integrity."""
import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair
from app.audit.writer import AuditWriter, WriterIntegrityError
from app.models import AuditEntry


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
async def test_writer_startup_detects_corrupted_last_entry(session_factory, node):
    from app.services.audit import AuditService

    async with session_factory() as session:
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
