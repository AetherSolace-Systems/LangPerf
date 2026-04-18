from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import FailureMode, Trajectory, TrajectoryFailureMode

router = APIRouter(tags=["failure_modes"])


def _fm_dto(fm: FailureMode) -> dict:
    return {
        "id": fm.id,
        "slug": fm.slug,
        "label": fm.label,
        "color": fm.color,
        "created_at": fm.created_at.isoformat(),
    }


class TagPayload(BaseModel):
    failure_mode_id: str


@router.get("/api/failure-modes")
async def list_failure_modes(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    result = await session.execute(
        select(FailureMode)
        .where(FailureMode.org_id == user.org_id)
        .order_by(FailureMode.created_at.asc())
    )
    return [_fm_dto(fm) for fm in result.scalars().all()]


@router.post("/api/trajectories/{trajectory_id}/failure-modes")
async def tag_trajectory(
    trajectory_id: str,
    payload: TagPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    fm = await session.get(FailureMode, payload.failure_mode_id)
    if fm is None or fm.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="failure mode not found")
    # idempotent: check if already tagged
    existing = await session.get(
        TrajectoryFailureMode,
        {"trajectory_id": trajectory_id, "failure_mode_id": payload.failure_mode_id},
    )
    if existing is None:
        session.add(
            TrajectoryFailureMode(
                trajectory_id=trajectory_id,
                failure_mode_id=payload.failure_mode_id,
                tagged_by=user.id,
            )
        )
        await session.commit()
    return _fm_dto(fm)


@router.get("/api/trajectories/{trajectory_id}/failure-modes")
async def list_trajectory_failure_modes(
    trajectory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    result = await session.execute(
        select(FailureMode)
        .join(TrajectoryFailureMode, TrajectoryFailureMode.failure_mode_id == FailureMode.id)
        .where(TrajectoryFailureMode.trajectory_id == trajectory_id)
        .order_by(FailureMode.created_at.asc())
    )
    return [_fm_dto(fm) for fm in result.scalars().all()]


@router.delete("/api/trajectories/{trajectory_id}/failure-modes/{failure_mode_id}", status_code=204)
async def detach_failure_mode(
    trajectory_id: str,
    failure_mode_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    link = await session.get(
        TrajectoryFailureMode,
        {"trajectory_id": trajectory_id, "failure_mode_id": failure_mode_id},
    )
    if link is not None:
        await session.delete(link)
        await session.commit()
    return Response(status_code=204)
