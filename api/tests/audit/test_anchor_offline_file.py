"""Offline-file anchor test — signer command is invoked, output persisted."""
import stat
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.audit.anchor.offline_file import OfflineFileAnchor
from app.audit.crypto import SIG_ED25519, generate_keypair
from app.models import ExternalAnchor
from app.services.audit import AuditService


@pytest.fixture
def node():
    priv, _ = generate_keypair(SIG_ED25519)
    return {"node_id": uuid.uuid4(), "priv": priv, "alg": SIG_ED25519}


@pytest.mark.asyncio
async def test_offline_file_anchor_runs_signer(tmp_path: Path, session, node):
    signer = tmp_path / "signer.sh"
    signer.write_text(
        "#!/bin/sh\n"
        "IN=$1\n"
        "OUT=$2\n"
        "printf 'SIGNED-' > $OUT && cat $IN >> $OUT\n"
    )
    signer.chmod(signer.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

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

    anchor = OfflineFileAnchor(
        signer_command=str(signer),
        work_dir=tmp_path / "work",
        anchor_ref="test-signer",
    )
    await anchor.anchor(session, root)

    rows = (await session.execute(select(ExternalAnchor))).scalars().all()
    assert len(rows) == 1
    expected = b"SIGNED-" + root.tree_size.to_bytes(8, "big") + root.root_hash
    assert rows[0].anchor_payload == expected
    assert rows[0].anchor_ref == "test-signer"
