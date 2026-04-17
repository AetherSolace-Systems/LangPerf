"""Node (span) patch endpoints — notes only in v1."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Span
from app.schemas import NodePatch, SpanOut

router = APIRouter(prefix="/api/nodes")


@router.patch("/{span_id}", response_model=SpanOut)
async def patch_node(
    span_id: str,
    patch: NodePatch,
    session: AsyncSession = Depends(get_session),
) -> SpanOut:
    span = await session.get(Span, span_id)
    if span is None:
        raise HTTPException(status_code=404, detail="span not found")

    if patch.clear_notes:
        span.notes = None
    elif patch.notes is not None:
        span.notes = patch.notes

    await session.commit()
    await session.refresh(span)
    return SpanOut.model_validate(span)
