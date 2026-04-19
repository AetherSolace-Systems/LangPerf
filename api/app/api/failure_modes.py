"""Failure-mode endpoints.

Thin HTTP-adapter layer — all business logic lives in
`app.services.failure_modes`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.services import failure_modes as failure_modes_service
from app.services.failure_modes import TagPayload

router = APIRouter(tags=["failure_modes"])


@router.get("/api/failure-modes")
async def list_failure_modes(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await failure_modes_service.list_failure_modes(session, org_id=user.org_id)


@router.post("/api/trajectories/{trajectory_id}/failure-modes")
async def tag_trajectory(
    trajectory_id: str,
    payload: TagPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await failure_modes_service.tag_trajectory(
        session,
        org_id=user.org_id,
        user_id=user.id,
        trajectory_id=trajectory_id,
        payload=payload,
    )


@router.get("/api/trajectories/{trajectory_id}/failure-modes")
async def list_trajectory_failure_modes(
    trajectory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await failure_modes_service.list_trajectory_failure_modes(
        session,
        org_id=user.org_id,
        trajectory_id=trajectory_id,
    )


@router.delete("/api/trajectories/{trajectory_id}/failure-modes/{failure_mode_id}", status_code=204)
async def detach_failure_mode(
    trajectory_id: str,
    failure_mode_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await failure_modes_service.detach_failure_mode(
        session,
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        failure_mode_id=failure_mode_id,
    )
    return Response(status_code=204)
