"""Offline file-signer external anchor.

Invokes a customer-configured signer command with two arguments:
an input file containing ``tree_size||root_hash`` and an output file
where the signer writes its signed attestation. Used in air-gap
deployments where the signer is a smartcard- or PIV-backed process.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.anchor.base import ExternalAnchorBackend
from app.models import AuditRoot, ExternalAnchor


class OfflineFileAnchor(ExternalAnchorBackend):
    anchor_type = "offline_file"

    def __init__(
        self,
        *,
        signer_command: str,
        work_dir: Path | str,
        anchor_ref: str | None = None,
    ) -> None:
        self._signer = signer_command
        self._work_dir = Path(work_dir)
        self._anchor_ref = anchor_ref

    async def anchor(self, session: AsyncSession, root: AuditRoot) -> ExternalAnchor:
        self._work_dir.mkdir(parents=True, exist_ok=True)
        in_path = self._work_dir / f"root-{root.tree_size}.bin"
        out_path = self._work_dir / f"root-{root.tree_size}.signed"
        in_path.write_bytes(root.tree_size.to_bytes(8, "big") + root.root_hash)

        proc = await asyncio.create_subprocess_exec(
            self._signer, str(in_path), str(out_path)
        )
        rc = await proc.wait()
        if rc != 0:
            raise RuntimeError(f"signer_command exited with {rc}")
        payload = out_path.read_bytes()

        row = ExternalAnchor(
            root_id=root.id,
            anchor_type=self.anchor_type,
            anchor_payload=payload,
            anchored_at=datetime.now(timezone.utc),
            anchor_ref=self._anchor_ref,
        )
        session.add(row)
        await session.flush()
        return row
