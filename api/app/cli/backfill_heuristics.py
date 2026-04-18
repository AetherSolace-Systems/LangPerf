import asyncio
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.heuristics.engine import evaluate_trajectory
from app.models import Trajectory


async def main(limit: int | None = None) -> None:
    async with SessionLocal() as db:
        q = select(Trajectory.id).order_by(Trajectory.started_at.desc())
        if limit:
            q = q.limit(limit)
        ids = [row[0] for row in (await db.execute(q)).all()]
    total = 0
    for tid in ids:
        async with SessionLocal() as db:
            total += await evaluate_trajectory(db, tid)
    print(f"evaluated {len(ids)} trajectories, wrote {total} hits")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(limit))
