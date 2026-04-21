"""Property test: chain continuity across many sequential appends."""
import uuid

import pytest
from sqlalchemy import select

from app.audit.crypto import SIG_ED25519, generate_keypair
from app.audit.hashing import compute_entry_hash
from app.models import AuditEntry
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

    # entry_hash recomputes from the stored columns.
    # Note: the ORM returns agent_id / principal_human_id as strings
    # (UUIDStr); convert back to UUID to access .bytes.
    # SQLite stores timestamps as naive datetimes; re-attach UTC to match the
    # service's ts_iso calculation (which used datetime.now(timezone.utc)).
    from datetime import timezone as tz

    for r in rows:
        # If ts is naive, attach UTC; if already aware, use as-is.
        ts = r.ts if r.ts.tzinfo is not None else r.ts.replace(tzinfo=tz.utc)
        ts_iso = ts.isoformat().replace("+00:00", "Z")
        expected = compute_entry_hash(
            seq=r.seq,
            prev_hash=r.prev_hash,
            event_hash=r.event_hash,
            agent_id=uuid.UUID(r.agent_id).bytes if r.agent_id else None,
            principal_human_id=uuid.UUID(r.principal_human_id).bytes if r.principal_human_id else None,
            ts_iso=ts_iso,
            agent_signature=r.agent_signature,
            ingest_signature=r.ingest_signature,
        )
        assert r.entry_hash == expected, f"seq={r.seq}: entry_hash mismatch"
