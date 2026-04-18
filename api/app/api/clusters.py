from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import HeuristicHit
from app.services.cluster import signature_hash, trajectory_signature

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("")
async def list_clusters(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
    limit: int = 50,
):
    rows = (await session.execute(
        select(HeuristicHit.trajectory_id, HeuristicHit.heuristic, HeuristicHit.signature)
        .where(HeuristicHit.org_id == user.org_id)
    )).all()

    by_traj: dict[str, list[dict]] = defaultdict(list)
    for tid, heuristic, sig in rows:
        by_traj[str(tid)].append({"heuristic": heuristic, "signature": sig})

    sig_to_trajs: dict[str, list[str]] = defaultdict(list)
    for tid, hits in by_traj.items():
        sig = trajectory_signature(hits)
        if not sig:
            continue
        sig_to_trajs[sig].append(tid)

    clusters = sorted(
        (
            {
                "id": signature_hash(sig),
                "signature": sig,
                "heuristics": sig.split("|"),
                "size": len(tids),
                "trajectory_ids": tids[:20],
            }
            for sig, tids in sig_to_trajs.items()
        ),
        key=lambda c: c["size"],
        reverse=True,
    )[:limit]
    return {"clusters": clusters}
