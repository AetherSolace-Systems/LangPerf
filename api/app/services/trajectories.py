"""Trajectory list / detail / patch service layer.

Extracted from `app.api.trajectories` to keep the HTTP-adapter layer thin.
Every function takes an `AsyncSession` plus keyword args and returns either
response schemas or raises `HTTPException` directly — mirroring the behaviour
of the inline code it replaced.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import ALLOWED_TAGS
from app.models import Span, Trajectory
from app.schemas import (
    FacetsResponse,
    TrajectoryDetail,
    TrajectoryListResponse,
    TrajectoryPatch,
    TrajectorySummary,
)


def apply_org_filters(
    stmt,
    *,
    org_id: str,
    tag: Optional[str] = None,
    service: Optional[str] = None,
    environment: Optional[str] = None,
    q: Optional[str] = None,
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


async def list_trajectories(
    session: AsyncSession,
    *,
    org_id: str,
    limit: int,
    offset: int,
    tag: Optional[str],
    service: Optional[str],
    environment: Optional[str],
    q: Optional[str],
) -> TrajectoryListResponse:
    base = apply_org_filters(
        select(Trajectory).where(Trajectory.org_id == org_id),
        org_id=org_id,
        tag=tag,
        service=service,
        environment=environment,
        q=q,
    )
    total = (
        await session.execute(
            apply_org_filters(
                select(func.count()).select_from(Trajectory).where(
                    Trajectory.org_id == org_id
                ),
                org_id=org_id,
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


async def get_facets(session: AsyncSession, *, org_id: str) -> FacetsResponse:
    services = (
        await session.execute(
            select(Trajectory.service_name)
            .where(Trajectory.service_name.is_not(None), Trajectory.org_id == org_id)
            .distinct()
            .order_by(Trajectory.service_name)
        )
    ).scalars().all()
    environments = (
        await session.execute(
            select(Trajectory.environment)
            .where(Trajectory.environment.is_not(None), Trajectory.org_id == org_id)
            .distinct()
            .order_by(Trajectory.environment)
        )
    ).scalars().all()
    tags = (
        await session.execute(
            select(Trajectory.status_tag)
            .where(Trajectory.status_tag.is_not(None), Trajectory.org_id == org_id)
            .distinct()
            .order_by(Trajectory.status_tag)
        )
    ).scalars().all()
    return FacetsResponse(
        services=[s for s in services if s],
        environments=[e for e in environments if e],
        tags=[t for t in tags if t],
    )


async def get_trajectory_detail(
    session: AsyncSession, *, org_id: str, trajectory_id: str
) -> TrajectoryDetail:
    result = await session.execute(
        select(Trajectory)
        .where(Trajectory.id == trajectory_id, Trajectory.org_id == org_id)
        .options(selectinload(Trajectory.spans))
    )
    traj = result.scalar_one_or_none()
    if traj is None:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return TrajectoryDetail.model_validate(traj)


async def patch_trajectory(
    session: AsyncSession,
    *,
    org_id: str,
    trajectory_id: str,
    payload: TrajectoryPatch,
) -> TrajectorySummary:
    result = await session.execute(
        select(Trajectory).where(
            Trajectory.id == trajectory_id, Trajectory.org_id == org_id
        )
    )
    traj = result.scalar_one_or_none()
    if traj is None:
        raise HTTPException(status_code=404, detail="trajectory not found")

    if payload.clear_tag:
        traj.status_tag = None
    elif payload.status_tag is not None:
        if payload.status_tag not in ALLOWED_TAGS:
            raise HTTPException(
                status_code=400,
                detail=f"status_tag must be one of {sorted(ALLOWED_TAGS)} (or use clear_tag=true)",
            )
        traj.status_tag = payload.status_tag

    if payload.clear_notes:
        traj.notes = None
    elif payload.notes is not None:
        traj.notes = payload.notes

    await session.commit()
    await session.refresh(traj)
    return TrajectorySummary.model_validate(traj)
