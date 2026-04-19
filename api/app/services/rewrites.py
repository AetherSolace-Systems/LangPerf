"""Rewrites service layer.

Extracted from `app.api.rewrites` to keep the HTTP-adapter layer thin. Every
function here takes an `AsyncSession` plus keyword args and returns the public
rewrite DTO (dict) or domain objects. The functions raise `HTTPException`
directly — mirroring the behaviour of the inline code they replaced — so the
route handlers can stay thin.
"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rewrite, Trajectory, User


class ProposedToolCall(BaseModel):
    kind: Literal["tool_call"]
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    reasoning: str | None = None


class ProposedFinalAnswer(BaseModel):
    kind: Literal["final_answer"]
    text: str


ProposedStep = ProposedToolCall | ProposedFinalAnswer


class CreateRewritePayload(BaseModel):
    branch_span_id: str = Field(min_length=1, max_length=255)
    rationale: str = ""
    proposed_steps: list[ProposedStep] = Field(default_factory=list)
    status: Literal["draft", "submitted"] = "draft"


class UpdateRewritePayload(BaseModel):
    rationale: str | None = None
    proposed_steps: list[ProposedStep] | None = None
    status: Literal["draft", "submitted"] | None = None


async def load_rewrite_dto(db: AsyncSession, r: Rewrite) -> dict:
    author = await db.get(User, r.author_id)
    return {
        "id": r.id,
        "trajectory_id": r.trajectory_id,
        "branch_span_id": r.branch_span_id,
        "author_id": r.author_id,
        "author_display_name": author.display_name if author else "unknown",
        "rationale": r.rationale,
        "proposed_steps": r.proposed_steps,
        "status": r.status,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


async def assert_trajectory(
    db: AsyncSession, *, trajectory_id: str, org_id: str
) -> Trajectory:
    t = await db.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return t


async def create_rewrite(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    trajectory_id: str,
    payload: CreateRewritePayload,
) -> dict:
    await assert_trajectory(session, trajectory_id=trajectory_id, org_id=org_id)
    r = Rewrite(
        org_id=org_id,
        trajectory_id=trajectory_id,
        branch_span_id=payload.branch_span_id,
        author_id=user_id,
        rationale=payload.rationale,
        proposed_steps=[s.model_dump() for s in payload.proposed_steps],
        status=payload.status,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return await load_rewrite_dto(session, r)


async def list_rewrites_for_trajectory(
    session: AsyncSession,
    *,
    org_id: str,
    trajectory_id: str,
) -> list[dict]:
    await assert_trajectory(session, trajectory_id=trajectory_id, org_id=org_id)
    rows = (await session.execute(
        select(Rewrite)
        .where(Rewrite.trajectory_id == trajectory_id)
        .order_by(Rewrite.created_at.desc())
    )).scalars().all()
    return [await load_rewrite_dto(session, r) for r in rows]


async def get_rewrite(
    session: AsyncSession,
    *,
    org_id: str,
    rewrite_id: str,
) -> dict:
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != org_id:
        raise HTTPException(status_code=404, detail="not found")
    return await load_rewrite_dto(session, r)


async def update_rewrite(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    is_admin: bool,
    rewrite_id: str,
    payload: UpdateRewritePayload,
) -> dict:
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != org_id:
        raise HTTPException(status_code=404, detail="not found")
    if r.author_id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="only the author can update")
    if payload.rationale is not None:
        r.rationale = payload.rationale
    if payload.proposed_steps is not None:
        r.proposed_steps = [s.model_dump() for s in payload.proposed_steps]
    if payload.status is not None:
        r.status = payload.status
    await session.commit()
    await session.refresh(r)
    return await load_rewrite_dto(session, r)


async def delete_rewrite(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    is_admin: bool,
    rewrite_id: str,
) -> None:
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != org_id:
        raise HTTPException(status_code=404, detail="not found")
    if r.author_id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="not allowed")
    await session.delete(r)
    await session.commit()
