"""AuditService — single mutation entry-point for the audit chain.

AuditService.append is the only path that writes audit_entries rows. All
future services that emit auditable events must call this before persisting
their own rows so the chain stays gapless. The session must be flushed (not
committed) here; the caller owns the transaction boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.canonical import canonical_encode
from app.audit.crypto import sign
from app.audit.hashing import compute_entry_hash, sha256
from app.models import AuditEntry


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        event_type: str,
        payload: dict,
        ingest_node_id: uuid.UUID,
        ingest_private_key: bytes,
        ingest_alg: str,
        agent_id: uuid.UUID | None = None,
        principal_human_id: uuid.UUID | None = None,
        agent_signature: bytes | None = None,
        agent_ts: datetime | None = None,
    ) -> AuditEntry:
        event_bytes = canonical_encode(payload)
        event_hash = sha256(event_bytes)

        prev = (
            await self._session.execute(
                select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1)
            )
        ).scalar_one_or_none()

        if prev is None:
            seq = 0
            prev_hash = bytes(32)
        else:
            seq = prev.seq + 1
            prev_hash = prev.entry_hash

        ts = datetime.now(timezone.utc)
        ts_iso = ts.isoformat().replace("+00:00", "Z")

        # Signed buffer binds seq + chain position + event identity + optional
        # agent claim. Using a nullable sentinel (0x00 vs 0x01+bytes) prevents
        # None from being pre-image-equivalent to any byte sequence.
        def _nullable(b: bytes | None) -> bytes:
            return b"\x00" if b is None else b"\x01" + b

        ingest_signed_buf = (
            seq.to_bytes(8, "big")
            + prev_hash
            + event_hash
            + _nullable(agent_signature)
        )
        ingest_signature = sign(ingest_private_key, ingest_signed_buf, ingest_alg)

        entry_hash = compute_entry_hash(
            seq=seq,
            prev_hash=prev_hash,
            event_hash=event_hash,
            agent_id=agent_id.bytes if agent_id else None,
            principal_human_id=principal_human_id.bytes if principal_human_id else None,
            ts_iso=ts_iso,
            agent_signature=agent_signature,
            ingest_signature=ingest_signature,
        )

        entry = AuditEntry(
            seq=seq,
            prev_hash=prev_hash,
            event_type=event_type,
            event_payload=event_bytes,
            event_hash=event_hash,
            entry_hash=entry_hash,
            agent_id=str(agent_id) if agent_id else None,
            principal_human_id=str(principal_human_id) if principal_human_id else None,
            agent_signature=agent_signature,
            ingest_node_id=str(ingest_node_id),
            ingest_signature=ingest_signature,
            ts=ts,
            agent_ts=agent_ts,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry
