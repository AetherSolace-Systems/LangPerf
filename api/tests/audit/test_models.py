"""Smoke tests for SQLAlchemy audit models — fields + relationships resolve."""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import AuditEntry, AuditRoot, ExternalAnchor


@pytest.mark.asyncio
async def test_insert_and_query_audit_entry(session):
    entry = AuditEntry(
        seq=0,
        prev_hash=bytes(32),
        event_type="genesis",
        event_payload=b"{}",
        event_hash=bytes(32),
        entry_hash=bytes(32),
        ingest_node_id=str(uuid.uuid4()),
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
        ingest_node_id=str(uuid.uuid4()),
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
