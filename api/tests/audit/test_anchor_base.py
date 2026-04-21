"""Anchor interface tests — 'none' anchor writes an ExternalAnchor row."""
import uuid

import pytest
from sqlalchemy import select

from app.audit.anchor.none_anchor import NoneAnchor
from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models import ExternalAnchor
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
