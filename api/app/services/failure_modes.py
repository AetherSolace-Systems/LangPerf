"""Failure-modes service layer.

Extracted from `app.api.failure_modes` to keep the HTTP-adapter layer thin.
Every function here takes an `AsyncSession` plus keyword args and returns the
public DTO (dict) or `None`. Functions raise `HTTPException` directly —
mirroring the behaviour of the inline code they replaced — so the route
handlers can stay thin.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FailureMode, Trajectory, TrajectoryFailureMode


class TagPayload(BaseModel):
    failure_mode_id: str


def failure_mode_to_dict(fm: FailureMode) -> dict:
    return {
        "id": fm.id,
        "slug": fm.slug,
        "label": fm.label,
        "color": fm.color,
        "created_at": fm.created_at.isoformat(),
    }


async def list_failure_modes(session: AsyncSession, *, org_id: str) -> list[dict]:
    result = await session.execute(
        select(FailureMode)
        .where(FailureMode.org_id == org_id)
        .order_by(FailureMode.created_at.asc())
    )
    return [failure_mode_to_dict(fm) for fm in result.scalars().all()]


async def tag_trajectory(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    trajectory_id: str,
    payload: TagPayload,
) -> dict:
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    fm = await session.get(FailureMode, payload.failure_mode_id)
    if fm is None or fm.org_id != org_id:
        raise HTTPException(status_code=404, detail="failure mode not found")
    # idempotent: check if already tagged
    existing = await session.get(
        TrajectoryFailureMode,
        {"trajectory_id": trajectory_id, "failure_mode_id": payload.failure_mode_id},
    )
    if existing is None:
        session.add(
            TrajectoryFailureMode(
                trajectory_id=trajectory_id,
                failure_mode_id=payload.failure_mode_id,
                tagged_by=user_id,
            )
        )
        await session.commit()
    return failure_mode_to_dict(fm)


async def list_trajectory_failure_modes(
    session: AsyncSession,
    *,
    org_id: str,
    trajectory_id: str,
) -> list[dict]:
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    result = await session.execute(
        select(FailureMode)
        .join(TrajectoryFailureMode, TrajectoryFailureMode.failure_mode_id == FailureMode.id)
        .where(TrajectoryFailureMode.trajectory_id == trajectory_id)
        .order_by(FailureMode.created_at.asc())
    )
    return [failure_mode_to_dict(fm) for fm in result.scalars().all()]


async def detach_failure_mode(
    session: AsyncSession,
    *,
    org_id: str,
    trajectory_id: str,
    failure_mode_id: str,
) -> None:
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    link = await session.get(
        TrajectoryFailureMode,
        {"trajectory_id": trajectory_id, "failure_mode_id": failure_mode_id},
    )
    if link is not None:
        await session.delete(link)
        await session.commit()
