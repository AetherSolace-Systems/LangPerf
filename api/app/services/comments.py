"""Comments service layer.

Extracted from `app.api.comments` to keep the HTTP-adapter layer thin. Every
function here takes an `AsyncSession` plus keyword args and returns the public
comment DTO (dict) or domain objects. The functions raise `HTTPException`
directly — mirroring the behaviour of the inline code they replaced — so the
route handlers can stay thin.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment, CommentMention, Notification, Trajectory, User
from app.services.mentions import dedupe, resolve_mentions


class CreateCommentPayload(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    parent_comment_id: str | None = None


class UpdateCommentPayload(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


async def load_comment_dto(db: AsyncSession, comment: Comment) -> dict:
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


async def assert_trajectory(
    db: AsyncSession, *, trajectory_id: str, org_id: str
) -> Trajectory:
    t = await db.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return t


async def create_span_comment(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    user_display_name: str,
    trajectory_id: str,
    span_id: str,
    payload: CreateCommentPayload,
) -> dict:
    await assert_trajectory(session, trajectory_id=trajectory_id, org_id=org_id)
    comment = Comment(
        org_id=org_id,
        trajectory_id=trajectory_id,
        span_id=span_id,
        author_id=user_id,
        body=payload.body,
        parent_comment_id=payload.parent_comment_id,
    )
    session.add(comment)
    await session.flush()

    mentioned = dedupe(await resolve_mentions(session, org_id, payload.body))
    for m in mentioned:
        if m.id == user_id:
            continue
        session.add(CommentMention(comment_id=comment.id, user_id=m.id))
        session.add(
            Notification(
                org_id=org_id,
                user_id=m.id,
                kind="mention",
                payload={
                    "comment_id": comment.id,
                    "trajectory_id": trajectory_id,
                    "span_id": span_id,
                    "author_display_name": user_display_name,
                    "excerpt": payload.body[:200],
                },
            )
        )

    await session.commit()
    await session.refresh(comment)
    return await load_comment_dto(session, comment)


async def list_span_comments(
    session: AsyncSession,
    *,
    org_id: str,
    trajectory_id: str,
    span_id: str,
) -> list[dict]:
    await assert_trajectory(session, trajectory_id=trajectory_id, org_id=org_id)
    result = await session.execute(
        select(Comment)
        .where(Comment.trajectory_id == trajectory_id, Comment.span_id == span_id)
        .order_by(Comment.created_at.asc())
    )
    return [await load_comment_dto(session, c) for c in result.scalars().all()]


async def list_trajectory_comments(
    session: AsyncSession,
    *,
    org_id: str,
    trajectory_id: str,
) -> list[dict]:
    await assert_trajectory(session, trajectory_id=trajectory_id, org_id=org_id)
    result = await session.execute(
        select(Comment)
        .where(Comment.trajectory_id == trajectory_id)
        .order_by(Comment.created_at.asc())
    )
    return [await load_comment_dto(session, c) for c in result.scalars().all()]


async def update_comment(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    comment_id: str,
    payload: UpdateCommentPayload,
) -> dict:
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != org_id:
        raise HTTPException(status_code=404, detail="not found")
    if comment.author_id != user_id:
        raise HTTPException(status_code=403, detail="not the author")
    comment.body = payload.body
    await session.commit()
    await session.refresh(comment)
    return await load_comment_dto(session, comment)


async def resolve_comment(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    comment_id: str,
) -> dict:
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != org_id:
        raise HTTPException(status_code=404, detail="not found")
    comment.resolved = True
    await session.commit()
    await session.refresh(comment)
    return await load_comment_dto(session, comment)


async def delete_comment(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    is_admin: bool,
    comment_id: str,
) -> None:
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != org_id:
        raise HTTPException(status_code=404, detail="not found")
    if comment.author_id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="not allowed")
    await session.delete(comment)
    await session.commit()
