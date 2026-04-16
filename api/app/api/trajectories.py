"""Trajectory list + detail endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Trajectory
from app.schemas import TrajectoryDetail, TrajectoryListResponse, TrajectorySummary

router = APIRouter(prefix="/api/trajectories")


@router.get("", response_model=TrajectoryListResponse)
async def list_trajectories(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> TrajectoryListResponse:
    total = (
        await session.execute(select(func.count()).select_from(Trajectory))
    ).scalar_one()
    result = await session.execute(
        select(Trajectory)
        .order_by(Trajectory.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    items = [TrajectorySummary.model_validate(t) for t in result.scalars().all()]
    return TrajectoryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{trajectory_id}", response_model=TrajectoryDetail)
async def get_trajectory(
    trajectory_id: str,
    session: AsyncSession = Depends(get_session),
) -> TrajectoryDetail:
    result = await session.execute(
        select(Trajectory)
        .where(Trajectory.id == trajectory_id)
        .options(selectinload(Trajectory.spans))
    )
    traj = result.scalar_one_or_none()
    if traj is None:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return TrajectoryDetail.model_validate(traj)
