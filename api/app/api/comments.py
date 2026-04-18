from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Comment, CommentMention, Notification, Trajectory, User
from app.services.mentions import dedupe, resolve_mentions

router = APIRouter(tags=["comments"])


class CreateCommentPayload(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    parent_comment_id: str | None = None


class UpdateCommentPayload(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


async def _load_dto(db: AsyncSession, comment: Comment) -> dict:
    author = await db.get(User, comment.author_id)
    return {
        "id": comment.id,
        "trajectory_id": comment.trajectory_id,
        "span_id": comment.span_id,
        "author_id": comment.author_id,
        "author_display_name": author.display_name if author else "unknown",
        "parent_comment_id": comment.parent_comment_id,
        "body": comment.body,
        "resolved": comment.resolved,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
    }


async def _assert_trajectory(db: AsyncSession, trajectory_id: str, org_id: str) -> Trajectory:
    t = await db.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return t


@router.post("/api/trajectories/{trajectory_id}/nodes/{span_id}/comments", status_code=201)
async def create_on_span(
    trajectory_id: str,
    span_id: str,
    payload: CreateCommentPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory(session, trajectory_id, user.org_id)
    comment = Comment(
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        span_id=span_id,
        author_id=user.id,
        body=payload.body,
        parent_comment_id=payload.parent_comment_id,
    )
    session.add(comment)
    await session.flush()

    mentioned = dedupe(await resolve_mentions(session, user.org_id, payload.body))
    for m in mentioned:
        if m.id == user.id:
            continue
        session.add(CommentMention(comment_id=comment.id, user_id=m.id))
        session.add(
            Notification(
                org_id=user.org_id,
                user_id=m.id,
                kind="mention",
                payload={
                    "comment_id": comment.id,
                    "trajectory_id": trajectory_id,
                    "span_id": span_id,
                    "author_display_name": user.display_name,
                    "excerpt": payload.body[:200],
                },
            )
        )

    await session.commit()
    await session.refresh(comment)
    return await _load_dto(session, comment)


@router.get("/api/trajectories/{trajectory_id}/nodes/{span_id}/comments")
async def list_on_span(
    trajectory_id: str,
    span_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory(session, trajectory_id, user.org_id)
    result = await session.execute(
        select(Comment)
        .where(Comment.trajectory_id == trajectory_id, Comment.span_id == span_id)
        .order_by(Comment.created_at.asc())
    )
    return [await _load_dto(session, c) for c in result.scalars().all()]


@router.get("/api/trajectories/{trajectory_id}/comments")
async def list_on_trajectory(
    trajectory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory(session, trajectory_id, user.org_id)
    result = await session.execute(
        select(Comment)
        .where(Comment.trajectory_id == trajectory_id)
        .order_by(Comment.created_at.asc())
    )
    return [await _load_dto(session, c) for c in result.scalars().all()]


@router.patch("/api/comments/{comment_id}")
async def update(
    comment_id: str,
    payload: UpdateCommentPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="not the author")
    comment.body = payload.body
    await session.commit()
    await session.refresh(comment)
    return await _load_dto(session, comment)


@router.post("/api/comments/{comment_id}/resolve")
async def resolve(
    comment_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    comment.resolved = True
    await session.commit()
    await session.refresh(comment)
    return await _load_dto(session, comment)


@router.delete("/api/comments/{comment_id}", status_code=204)
async def delete(
    comment_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if comment.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="not allowed")
    await session.delete(comment)
    await session.commit()
    return Response(status_code=204)
