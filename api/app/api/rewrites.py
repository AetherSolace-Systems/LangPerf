from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Rewrite, Trajectory, User

router = APIRouter(tags=["rewrites"])


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


async def _dto(db: AsyncSession, r: Rewrite) -> dict:
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


async def _assert_trajectory(db: AsyncSession, trajectory_id: str, org_id: str) -> Trajectory:
    t = await db.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return t


@router.post("/api/trajectories/{trajectory_id}/rewrites", status_code=201)
async def create(
    trajectory_id: str,
    payload: CreateRewritePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory(session, trajectory_id, user.org_id)
    r = Rewrite(
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        branch_span_id=payload.branch_span_id,
        author_id=user.id,
        rationale=payload.rationale,
        proposed_steps=[s.model_dump() for s in payload.proposed_steps],
        status=payload.status,
    )
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return await _dto(session, r)


@router.get("/api/trajectories/{trajectory_id}/rewrites")
async def list_for_trajectory(
    trajectory_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory(session, trajectory_id, user.org_id)
    rows = (await session.execute(
        select(Rewrite)
        .where(Rewrite.trajectory_id == trajectory_id)
        .order_by(Rewrite.created_at.desc())
    )).scalars().all()
    return [await _dto(session, r) for r in rows]


@router.get("/api/rewrites/{rewrite_id}")
async def get_one(
    rewrite_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    return await _dto(session, r)


@router.patch("/api/rewrites/{rewrite_id}")
async def update(
    rewrite_id: str,
    payload: UpdateRewritePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if r.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="only the author can update")
    if payload.rationale is not None:
        r.rationale = payload.rationale
    if payload.proposed_steps is not None:
        r.proposed_steps = [s.model_dump() for s in payload.proposed_steps]
    if payload.status is not None:
        r.status = payload.status
    await session.commit()
    await session.refresh(r)
    return await _dto(session, r)


@router.delete("/api/rewrites/{rewrite_id}", status_code=204)
async def delete(
    rewrite_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    r = await session.get(Rewrite, rewrite_id)
    if r is None or r.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if r.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="not allowed")
    await session.delete(r)
    await session.commit()
    return Response(status_code=204)
