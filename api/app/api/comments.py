"""Comment endpoints.

Thin HTTP-adapter layer — all business logic lives in `app.services.comments`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.services import comments as comments_service
from app.services.comments import CreateCommentPayload, UpdateCommentPayload

router = APIRouter(tags=["comments"])


@router.post("/api/trajectories/{trajectory_id}/nodes/{span_id}/comments", status_code=201)
async def create_on_span(
    trajectory_id: str,
    span_id: str,
    payload: CreateCommentPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await comments_service.create_span_comment(
        session,
        org_id=user.org_id,
        user_id=user.id,
        user_display_name=user.display_name,
        trajectory_id=trajectory_id,
        span_id=span_id,
        payload=payload,
    )


@router.get("/api/trajectories/{trajectory_id}/nodes/{span_id}/comments")
async def list_on_span(
    trajectory_id: str,
    span_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await comments_service.list_span_comments(
        session,
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        span_id=span_id,
    )


@router.get("/api/trajectories/{trajectory_id}/comments")
async def list_on_trajectory(
    trajectory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await comments_service.list_trajectory_comments(
        session,
        org_id=user.org_id,
        trajectory_id=trajectory_id,
    )


@router.patch("/api/comments/{comment_id}")
async def update(
    comment_id: str,
    payload: UpdateCommentPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await comments_service.update_comment(
        session,
        org_id=user.org_id,
        user_id=user.id,
        comment_id=comment_id,
        payload=payload,
    )


@router.post("/api/comments/{comment_id}/resolve")
async def resolve(
    comment_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    return await comments_service.resolve_comment(
        session,
        org_id=user.org_id,
        user_id=user.id,
        comment_id=comment_id,
    )


@router.delete("/api/comments/{comment_id}", status_code=204)
async def delete(
    comment_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await comments_service.delete_comment(
        session,
        org_id=user.org_id,
        user_id=user.id,
        is_admin=user.is_admin,
        comment_id=comment_id,
    )
    return Response(status_code=204)
