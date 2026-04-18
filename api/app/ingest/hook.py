import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.heuristics.engine import evaluate_trajectory

logger = logging.getLogger(__name__)


async def run_heuristics_for_trajectories(
    session_factory: async_sessionmaker, trajectory_ids: list[str]
) -> None:
    for tid in trajectory_ids:
        try:
            async with session_factory() as db:
                await evaluate_trajectory(db, tid)
        except Exception as exc:
            logger.exception("heuristic evaluation failed for %s: %s", tid, exc)


def schedule_heuristics(
    session_factory: async_sessionmaker, trajectory_ids: list[str]
) -> None:
    if not trajectory_ids:
        return
    asyncio.create_task(run_heuristics_for_trajectories(session_factory, trajectory_ids))
