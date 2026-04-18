"""Node (span) patch endpoints — notes only in v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import require_user
from app.db import get_session
from app.models import Span, Trajectory
from app.schemas import NodePatch, SpanOut

router = APIRouter(prefix="/api/nodes")


@router.patch("/{span_id}", response_model=SpanOut)
async def patch_node(
    span_id: str,
    patch: NodePatch,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> SpanOut:
    # Load the span and its parent trajectory together to enforce org_id scoping.
    result = await session.execute(
        select(Span)
        .where(Span.span_id == span_id)
        .options(selectinload(Span.trajectory))
    )
    span = result.scalar_one_or_none()
    if span is None:
        raise HTTPException(status_code=404, detail="span not found")

    # Verify the parent trajectory belongs to this user's org.
    if span.trajectory is None or span.trajectory.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="span not found")

    if patch.clear_notes:
        span.notes = None
    elif patch.notes is not None:
        span.notes = patch.notes

    await session.commit()
    await session.refresh(span)
    return SpanOut.model_validate(span)
