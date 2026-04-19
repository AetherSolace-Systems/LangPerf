"""Rewrite endpoints.

Thin HTTP-adapter layer — all business logic lives in `app.services.rewrites`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.services import rewrites as rewrites_service
from app.services.rewrites import CreateRewritePayload, UpdateRewritePayload

router = APIRouter(tags=["rewrites"])


@router.post("/api/trajectories/{trajectory_id}/rewrites", status_code=201)
async def create(
    trajectory_id: str,
    payload: CreateRewritePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await rewrites_service.create_rewrite(
        session,
        org_id=user.org_id,
        user_id=user.id,
        trajectory_id=trajectory_id,
        payload=payload,
    )


@router.get("/api/trajectories/{trajectory_id}/rewrites")
async def list_for_trajectory(
    trajectory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await rewrites_service.list_rewrites_for_trajectory(
        session,
        org_id=user.org_id,
        trajectory_id=trajectory_id,
    )


@router.get("/api/rewrites/{rewrite_id}")
async def get_one(
    rewrite_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await rewrites_service.get_rewrite(
        session,
        org_id=user.org_id,
        rewrite_id=rewrite_id,
    )


@router.patch("/api/rewrites/{rewrite_id}")
async def update(
    rewrite_id: str,
    payload: UpdateRewritePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await rewrites_service.update_rewrite(
        session,
        org_id=user.org_id,
        user_id=user.id,
        is_admin=user.is_admin,
        rewrite_id=rewrite_id,
        payload=payload,
    )


@router.delete("/api/rewrites/{rewrite_id}", status_code=204)
async def delete(
    rewrite_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await rewrites_service.delete_rewrite(
        session,
        org_id=user.org_id,
        user_id=user.id,
        is_admin=user.is_admin,
        rewrite_id=rewrite_id,
    )
    return Response(status_code=204)
