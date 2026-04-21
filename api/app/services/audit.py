"""AuditService — single mutation entry-point for the audit chain.

AuditService.append is the only path that writes audit_entries rows. All
future services that emit auditable events must call this before persisting
their own rows so the chain stays gapless. The session must be flushed (not
committed) here; the caller owns the transaction boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.canonical import canonical_encode
from app.audit.crypto import sign
from app.audit.hashing import compute_entry_hash, compute_leaf_hash, sha256
from app.audit.merkle import merkle_root
from app.models import AuditEntry, AuditRoot


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
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

        # Baseline path — known-unsafe under concurrency. Two simultaneous
        # appends can both read seq=0 and both try to INSERT seq=1, violating
        # the UNIQUE constraint. Task 11 (Writer) serializes via an in-process
        # queue with a single leader-elected writer.
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

    async def snapshot_root(
        self,
        *,
        ingest_node_id: uuid.UUID,
        ingest_private_key: bytes,
        ingest_alg: str,
    ) -> AuditRoot:
        entry_hashes = (
            await self._session.execute(
                select(AuditEntry.entry_hash).order_by(AuditEntry.seq)
            )
        ).scalars().all()
        tree_size = len(entry_hashes)
        if tree_size == 0:
            raise ValueError("cannot snapshot root of empty log")
        leaves = [compute_leaf_hash(h) for h in entry_hashes]
        root_hash = merkle_root(leaves)
        signed = tree_size.to_bytes(8, "big") + root_hash
        sig = sign(ingest_private_key, signed, ingest_alg)
        root = AuditRoot(
            tree_size=tree_size,
            root_hash=root_hash,
            computed_at=datetime.now(timezone.utc),
            ingest_node_id=str(ingest_node_id),
            ingest_signature=sig,
        )
        self._session.add(root)
        await self._session.flush()
        return root

    async def get_inclusion_proof(self, *, seq: int, tree_size: int) -> list[bytes]:
        entry_hashes = (
            await self._session.execute(
                select(AuditEntry.entry_hash)
                .where(AuditEntry.seq < tree_size)
                .order_by(AuditEntry.seq)
            )
        ).scalars().all()
        leaves = [compute_leaf_hash(h) for h in entry_hashes]
        from app.audit.merkle import inclusion_proof as _inclusion_proof
        return _inclusion_proof(leaves, seq)

    async def get_consistency_proof(self, *, old_size: int, new_size: int) -> list[bytes]:
        entry_hashes = (
            await self._session.execute(
                select(AuditEntry.entry_hash)
                .where(AuditEntry.seq < new_size)
                .order_by(AuditEntry.seq)
            )
        ).scalars().all()
        leaves = [compute_leaf_hash(h) for h in entry_hashes]
        from app.audit.merkle import consistency_proof as _consistency_proof
        return _consistency_proof(leaves, old_size)

    async def recent_root(self) -> AuditRoot | None:
        return (
            await self._session.execute(
                select(AuditRoot).order_by(AuditRoot.tree_size.desc()).limit(1)
            )
        ).scalar_one_or_none()
