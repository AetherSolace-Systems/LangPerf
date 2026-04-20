"""Trajectory list + detail + patch endpoints.

Thin HTTP-adapter layer — all query / mutation logic lives in
`app.services.trajectories`.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.schemas import (
    FacetsResponse,
    TrajectoryDetail,
    TrajectoryListResponse,
    TrajectoryPatch,
    TrajectorySummary,
)
from app.services import trajectories as trajectories_service

router = APIRouter(prefix="/api/trajectories")


@router.get("", response_model=TrajectoryListResponse)
async def list_trajectories(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    tag: Optional[str] = Query(default=None, description="good|bad|interesting|todo|none"),
    service: Optional[str] = Query(default=None),
    environment: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, description="free-text search"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> TrajectoryListResponse:
    return await trajectories_service.list_trajectories(
        session,
        org_id=user.org_id,
        limit=limit,
        offset=offset,
        tag=tag,
        service=service,
        environment=environment,
        q=q,
    )


@router.get("/facets", response_model=FacetsResponse)
async def get_facets(
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> FacetsResponse:
    return await trajectories_service.get_facets(session, org_id=user.org_id)


@router.get("/{trajectory_id}", response_model=TrajectoryDetail)
async def get_trajectory(
    trajectory_id: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> TrajectoryDetail:
    return await trajectories_service.get_trajectory_detail(
        session, org_id=user.org_id, trajectory_id=trajectory_id
    )


@router.patch("/{trajectory_id}", response_model=TrajectorySummary)
async def patch_trajectory(
    trajectory_id: str,
    patch: TrajectoryPatch,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> TrajectorySummary:
    return await trajectories_service.patch_trajectory(
        session, org_id=user.org_id, trajectory_id=trajectory_id, payload=patch
    )
