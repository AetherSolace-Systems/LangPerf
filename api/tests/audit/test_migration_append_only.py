"""Verify the 0017 migration creates tables and the append-only trigger.

Under sqlite the test suite builds tables via Base.metadata.create_all(), not
Alembic migrations, so audit_entries / audit_roots / external_anchors won't
exist until Task 8 adds the SQLAlchemy models.  The table-existence test is
therefore skipped under sqlite; test_models.py in Task 8 will be the
canonical sqlite verification.  The trigger test requires Postgres regardless.
"""
import os

import pytest
import sqlalchemy as sa

USING_POSTGRES = os.environ.get("TEST_DATABASE_URL", "").startswith("postgres")


@pytest.mark.asyncio
@pytest.mark.skipif(not USING_POSTGRES, reason="audit tables only exist under Postgres (Alembic lane); sqlite uses Base.metadata.create_all — models land in Task 8")
async def test_audit_tables_exist(session):
    await session.execute(sa.text("SELECT COUNT(*) FROM audit_entries"))
    await session.execute(sa.text("SELECT COUNT(*) FROM audit_roots"))
    await session.execute(sa.text("SELECT COUNT(*) FROM external_anchors"))


@pytest.mark.asyncio
@pytest.mark.skipif(not USING_POSTGRES, reason="append-only trigger is Postgres-only")
async def test_audit_entries_update_rejected(session):
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
