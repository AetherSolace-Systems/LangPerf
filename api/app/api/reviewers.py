from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Notification, Trajectory, User

router = APIRouter(tags=["reviewers"])


class AssignPayload(BaseModel):
    user_id: str | None


@router.post("/api/trajectories/{trajectory_id}/assign")
async def assign_reviewer(
    trajectory_id: str,
    payload: AssignPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")

    if payload.user_id is not None:
        target = await session.get(User, payload.user_id)
        if target is None or target.org_id != user.org_id:
            raise HTTPException(status_code=400, detail="target user not in same org")
        t.assigned_user_id = target.id
        # Create notification for assignee
        session.add(
            Notification(
                org_id=user.org_id,
                user_id=target.id,
                kind="assigned",
                payload={
                    "trajectory_id": trajectory_id,
                    "assigned_by": user.id,
                },
            )
        )
    else:
        t.assigned_user_id = None

    await session.commit()
    await session.refresh(t)
    return {"trajectory_id": t.id, "assigned_user_id": t.assigned_user_id}
