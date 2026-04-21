"""Writer leader-election tests."""
import pytest

from app.audit.leader import WRITER_LOCK_KEY, acquire_writer_lock


@pytest.mark.asyncio
async def test_acquire_writer_lock_is_exclusive(session_factory):
    async with session_factory() as s1, session_factory() as s2:
        got1 = await acquire_writer_lock(s1, WRITER_LOCK_KEY)
        got2 = await acquire_writer_lock(s2, WRITER_LOCK_KEY)
        assert got1 is True
        assert got2 is False


@pytest.mark.asyncio
async def test_writer_lock_released_on_session_close(session_factory):
    async with session_factory() as s1:
        got1 = await acquire_writer_lock(s1, WRITER_LOCK_KEY)
        assert got1 is True
    async with session_factory() as s2:
        got2 = await acquire_writer_lock(s2, WRITER_LOCK_KEY)
        assert got2 is True
