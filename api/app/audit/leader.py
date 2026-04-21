"""Writer leader-election via Postgres session-scoped advisory locks.

Falls back to an in-process lock on sqlite (tests). The lock is held for
the lifetime of the session; closing the session releases the lock.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

WRITER_LOCK_KEY = 0x73_65_6E_74_69  # "senti" ASCII

_sqlite_lock = asyncio.Lock()
_sqlite_held: set[int] = set()


async def acquire_writer_lock(session: AsyncSession, key: int) -> bool:
    dialect = session.bind.dialect.name if session.bind else ""
    if dialect == "postgresql":
        result = await session.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
        return bool(result.scalar())
    async with _sqlite_lock:
        if key in _sqlite_held:
            return False
        _sqlite_held.add(key)

        original_close = session.close

        async def _release_and_close():
            _sqlite_held.discard(key)
            await original_close()

        session.close = _release_and_close  # type: ignore[method-assign]
        return True
