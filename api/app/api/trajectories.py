"""Trajectory list + detail + patch endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import ALLOWED_TAGS
from app.db import get_session
from app.models import Span, Trajectory
from app.schemas import (
    FacetsResponse,
    TrajectoryDetail,
    TrajectoryListResponse,
    TrajectoryPatch,
    TrajectorySummary,
)

router = APIRouter(prefix="/api/trajectories")


def _apply_filters(
    stmt,
    *,
    tag: Optional[str],
    service: Optional[str],
    environment: Optional[str],
    q: Optional[str],
):
    if tag == "none":
        stmt = stmt.where(Trajectory.status_tag.is_(None))
    elif tag:
        stmt = stmt.where(Trajectory.status_tag == tag)
    if service:
        stmt = stmt.where(Trajectory.service_name == service)
    if environment:
        stmt = stmt.where(Trajectory.environment == environment)
    if q:
        pattern = f"%{q}%"
        # Match trajectory name, notes, or any span attribute text (slow but ok at
        # dogfood scale — replace with tsvector + GIN later if needed).
        span_match = (
            select(Span.trajectory_id)
            .where(cast(Span.attributes, String).ilike(pattern))
            .distinct()
        )
        stmt = stmt.where(
            or_(
                Trajectory.name.ilike(pattern),
                Trajectory.notes.ilike(pattern),
                Trajectory.id.in_(span_match),
            )
        )
    return stmt


@router.get("", response_model=TrajectoryListResponse)
async def list_trajectories(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tag: Optional[str] = Query(default=None, description="good|bad|interesting|todo|none"),
    service: Optional[str] = Query(default=None),
    environment: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="free-text search"),
    session: AsyncSession = Depends(get_session),
) -> TrajectoryListResponse:
    base = _apply_filters(
        select(Trajectory),
        tag=tag,
        service=service,
        environment=environment,
        q=q,
    )
    total = (
        await session.execute(
            _apply_filters(
                select(func.count()).select_from(Trajectory),
                tag=tag,
                service=service,
                environment=environment,
                q=q,
            )
        )
    ).scalar_one()
    result = await session.execute(
        base.order_by(Trajectory.started_at.desc()).limit(limit).offset(offset)
    )
    items = [TrajectorySummary.model_validate(t) for t in result.scalars().all()]
    return TrajectoryListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/facets", response_model=FacetsResponse)
async def get_facets(session: AsyncSession = Depends(get_session)) -> FacetsResponse:
    services = (
        await session.execute(
            select(Trajectory.service_name)
            .where(Trajectory.service_name.is_not(None))
            .distinct()
            .order_by(Trajectory.service_name)
        )
    ).scalars().all()
    environments = (
        await session.execute(
            select(Trajectory.environment)
            .where(Trajectory.environment.is_not(None))
            .distinct()
            .order_by(Trajectory.environment)
        )
    ).scalars().all()
    tags = (
        await session.execute(
            select(Trajectory.status_tag)
            .where(Trajectory.status_tag.is_not(None))
            .distinct()
            .order_by(Trajectory.status_tag)
        )
    ).scalars().all()
    return FacetsResponse(
        services=[s for s in services if s],
        environments=[e for e in environments if e],
        tags=[t for t in tags if t],
    )


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


@router.patch("/{trajectory_id}", response_model=TrajectorySummary)
async def patch_trajectory(
    trajectory_id: str,
    patch: TrajectoryPatch,
    session: AsyncSession = Depends(get_session),
) -> TrajectorySummary:
    traj = await session.get(Trajectory, trajectory_id)
    if traj is None:
        raise HTTPException(status_code=404, detail="trajectory not found")

    if patch.clear_tag:
        traj.status_tag = None
    elif patch.status_tag is not None:
        if patch.status_tag not in ALLOWED_TAGS:
            raise HTTPException(
                status_code=400,
                detail=f"status_tag must be one of {sorted(ALLOWED_TAGS)} (or use clear_tag=true)",
            )
        traj.status_tag = patch.status_tag

    if patch.clear_notes:
        traj.notes = None
    elif patch.notes is not None:
        traj.notes = patch.notes

    await session.commit()
    await session.refresh(traj)
    return TrajectorySummary.model_validate(traj)
