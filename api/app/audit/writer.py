"""Single-Writer audit submission queue.

The Writer owns the in-memory chain-state cache (``last_seq``,
``last_entry_hash``) and batches submissions into one transaction per
flush cycle. Exactly one Writer exists per deployment; leader election
is handled externally (Task 12).
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import select

from app.audit.canonical import canonical_encode
from app.audit.crypto import sign
from app.audit.hashing import compute_entry_hash, sha256
from app.models import AuditEntry


class WriterIntegrityError(Exception):
    """Persisted chain state diverges from what the Writer can reconstruct."""


@dataclass
class _Submission:
    event_type: str
    payload: dict[str, Any]
    agent_id: uuid.UUID | None
    principal_human_id: uuid.UUID | None
    agent_signature: bytes | None
    agent_ts: datetime | None
    future: asyncio.Future


def _uuid_bytes_or_none(v) -> bytes | None:
    """Accept either a uuid.UUID or a str returned by the ORM; return 16 bytes or None."""
    if v is None:
        return None
    if isinstance(v, uuid.UUID):
        return v.bytes
    return uuid.UUID(str(v)).bytes


def _ts_iso(v: datetime) -> str:
    ts = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return ts.isoformat().replace("+00:00", "Z")


class AuditWriter:
    def __init__(
        self,
        *,
        session_factory: Callable,
        ingest_node_id: uuid.UUID,
        ingest_private_key: bytes,
        ingest_alg: str,
        batch_size: int = 500,
        flush_interval_ms: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._node_id = ingest_node_id
        self._priv = ingest_private_key
        self._alg = ingest_alg
        self._batch_size = batch_size
        self._flush_interval_ms = flush_interval_ms

        self._queue: asyncio.Queue[_Submission] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._last_seq: int = -1
        self._last_entry_hash: bytes = bytes(32)

    async def start(self) -> None:
        await self._load_and_verify_chain_state()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        # Drain queued submissions before cancelling so in-flight work completes.
        await self._drain_queue()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def submit(
        self,
        *,
        event_type: str,
        payload: dict[str, Any],
        agent_id: uuid.UUID | None = None,
        principal_human_id: uuid.UUID | None = None,
        agent_signature: bytes | None = None,
        agent_ts: datetime | None = None,
    ) -> AuditEntry:
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        await self._queue.put(
            _Submission(
                event_type=event_type,
                payload=payload,
                agent_id=agent_id,
                principal_human_id=principal_human_id,
                agent_signature=agent_signature,
                agent_ts=agent_ts,
                future=fut,
            )
        )
        return await fut

    async def _drain_queue(self) -> None:
        """Flush all queued submissions before shutdown."""
        while not self._queue.empty():
            batch: list[_Submission] = []
            while not self._queue.empty() and len(batch) < self._batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            if batch:
                try:
                    await self._flush(batch)
                except Exception as exc:  # noqa: BLE001
                    for sub in batch:
                        if not sub.future.done():
                            sub.future.set_exception(exc)

    async def _load_and_verify_chain_state(self) -> None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(AuditEntry).order_by(AuditEntry.seq.desc()).limit(1)
                )
            ).scalar_one_or_none()
            if row is None:
                return
            expected = compute_entry_hash(
                seq=row.seq,
                prev_hash=row.prev_hash,
                event_hash=row.event_hash,
                agent_id=_uuid_bytes_or_none(row.agent_id),
                principal_human_id=_uuid_bytes_or_none(row.principal_human_id),
                ts_iso=_ts_iso(row.ts),
                agent_signature=row.agent_signature,
                ingest_signature=row.ingest_signature,
            )
            if expected != row.entry_hash:
                raise WriterIntegrityError(
                    f"entry_hash mismatch at seq={row.seq}: persisted value does not recompute"
                )
            self._last_seq = row.seq
            self._last_entry_hash = row.entry_hash

    async def _run(self) -> None:
        while True:
            batch: list[_Submission] = [await self._queue.get()]
            deadline = asyncio.get_event_loop().time() + self._flush_interval_ms / 1000
            while len(batch) < self._batch_size:
                timeout = deadline - asyncio.get_event_loop().time()
                if timeout <= 0:
                    break
                try:
                    batch.append(await asyncio.wait_for(self._queue.get(), timeout=timeout))
                except asyncio.TimeoutError:
                    break
            try:
                await self._flush(batch)
            except Exception as exc:  # noqa: BLE001
                for sub in batch:
                    if not sub.future.done():
                        sub.future.set_exception(exc)

    async def _flush(self, batch: list[_Submission]) -> None:
        async with self._session_factory() as session:
            rows: list[AuditEntry] = []
            for sub in batch:
                event_bytes = canonical_encode(sub.payload)
                event_hash = sha256(event_bytes)
                seq = self._last_seq + 1
                prev_hash = self._last_entry_hash
                ts = datetime.now(timezone.utc)
                ts_iso = _ts_iso(ts)

                ingest_signed_buf = (
                    seq.to_bytes(8, "big")
                    + prev_hash
                    + event_hash
                    + (b"\x00" if sub.agent_signature is None else b"\x01" + sub.agent_signature)
                )
                ingest_signature = sign(self._priv, ingest_signed_buf, self._alg)

                entry_hash = compute_entry_hash(
                    seq=seq,
                    prev_hash=prev_hash,
                    event_hash=event_hash,
                    agent_id=sub.agent_id.bytes if sub.agent_id else None,
                    principal_human_id=sub.principal_human_id.bytes
                    if sub.principal_human_id
                    else None,
                    ts_iso=ts_iso,
                    agent_signature=sub.agent_signature,
                    ingest_signature=ingest_signature,
                )

                row = AuditEntry(
                    seq=seq,
                    prev_hash=prev_hash,
                    event_type=sub.event_type,
                    event_payload=event_bytes,
                    event_hash=event_hash,
                    entry_hash=entry_hash,
                    agent_id=str(sub.agent_id) if sub.agent_id else None,
                    principal_human_id=str(sub.principal_human_id)
                    if sub.principal_human_id
                    else None,
                    agent_signature=sub.agent_signature,
                    ingest_node_id=str(self._node_id),
                    ingest_signature=ingest_signature,
                    ts=ts,
                    agent_ts=sub.agent_ts,
                )
                session.add(row)
                rows.append(row)
                self._last_seq = seq
                self._last_entry_hash = entry_hash
            await session.commit()
        for sub, row in zip(batch, rows, strict=True):
            if not sub.future.done():
                sub.future.set_result(row)
