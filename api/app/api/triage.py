from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import HeuristicHit, Trajectory

router = APIRouter(prefix="/api/queue", tags=["triage"])


@router.get("")
async def queue(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
    heuristic: list[str] = Query(default_factory=list),
    assigned_to_me: bool = False,
    limit: int = 50,
    offset: int = 0,
):
    # Using min(severity, 1.0) as per-hit clamp to avoid any single hot-spot dominating score.
    # SQLite lacks LEAST(); use CASE instead for portability.
    from sqlalchemy import case
    clamped = func.sum(
        case((HeuristicHit.severity > 1.0, 1.0), else_=HeuristicHit.severity)
    ).label("score")

    base = (
        select(Trajectory, clamped, func.count(HeuristicHit.id).label("hit_count"))
        .join(HeuristicHit, HeuristicHit.trajectory_id == Trajectory.id)
        .where(Trajectory.org_id == user.org_id)
        .group_by(Trajectory.id)
    )
    if heuristic:
        base = base.where(HeuristicHit.heuristic.in_(heuristic))
    if assigned_to_me:
        base = base.where(Trajectory.assigned_user_id == user.id)

    base = base.order_by(clamped.desc(), Trajectory.started_at.desc()).limit(limit).offset(offset)
    results = (await session.execute(base)).all()

    items = []
    for traj, score, hit_count in results:
        hits_q = select(HeuristicHit).where(HeuristicHit.trajectory_id == traj.id)
        hits = (await session.execute(hits_q)).scalars().all()
        items.append({
            "trajectory_id": traj.id,
            "name": traj.name,
            "service_name": traj.service_name,
            "started_at": traj.started_at.isoformat() if traj.started_at else None,
            "assigned_user_id": traj.assigned_user_id,
            "score": float(score),
            "hit_count": hit_count,
            "hits": [
                {
                    "heuristic": h.heuristic,
                    "severity": h.severity,
                    "signature": h.signature,
                    "details": h.details,
                }
                for h in hits
            ],
        })
    return {"items": items, "total": len(items), "offset": offset, "limit": limit}


@router.get("/{trajectory_id}/hits", tags=["triage"])
async def hits_for_trajectory(
    trajectory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    rows = (await session.execute(
        select(HeuristicHit).where(
            HeuristicHit.trajectory_id == trajectory_id, HeuristicHit.org_id == user.org_id
        ).order_by(HeuristicHit.severity.desc())
    )).scalars().all()
    return [
        {
            "heuristic": h.heuristic, "severity": h.severity,
            "signature": h.signature, "details": h.details,
        }
        for h in rows
    ]
