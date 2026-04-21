"""RFC 3161 TSA anchor test — a fake TSA echoes a fixed TimeStampToken blob."""
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.audit.anchor.rfc3161 import RFC3161Anchor
from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models import ExternalAnchor
from app.services.audit import AuditService


@pytest.fixture
def node():
    priv, _ = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "alg": SIG_ED25519}


@pytest.mark.asyncio
async def test_rfc3161_anchor_posts_request_and_stores_response(session, node):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Content-Type"] == "application/timestamp-query"
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
    await anchor.anchor(session, root)

    rows = (await session.execute(select(ExternalAnchor))).scalars().all()
    assert len(rows) == 1
    assert rows[0].anchor_type == "rfc3161_tsa"
    assert rows[0].anchor_payload == b"FAKE-TSR-BLOB"
    assert rows[0].anchor_ref == "tsa.example"
