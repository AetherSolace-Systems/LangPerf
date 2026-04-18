from app.ingest.hook import schedule_heuristics
from app.db import SessionLocal


async def test_schedule_heuristics_handles_empty_list():
    # No crash on empty list
    schedule_heuristics(SessionLocal, [])


async def test_schedule_heuristics_accepts_list():
    # Smoke test — doesn't crash when scheduling (task fires and forgets)
    schedule_heuristics(SessionLocal, ["fake-id-that-does-not-exist"])
    import asyncio
    await asyncio.sleep(0.01)  # let the task run briefly; it'll log an exception and move on
