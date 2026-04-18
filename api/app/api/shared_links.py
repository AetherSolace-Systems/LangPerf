import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import SharedLink, Trajectory

router = APIRouter(tags=["shared_links"])


class SharePayload(BaseModel):
    expires_in_days: int | None = 30


@router.post("/api/trajectories/{trajectory_id}/share", status_code=201)
async def create_shared_link(
    trajectory_id: str,
    payload: SharePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")

    token = secrets.token_urlsafe(32)
    expires_at = None
    if payload.expires_in_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)

    link = SharedLink(
        token=token,
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        created_by=user.id,
        expires_at=expires_at,
    )
    session.add(link)
    await session.commit()
    return {
        "token": token,
        "trajectory_id": trajectory_id,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


@router.post("/api/shared/{link_token}/revoke", status_code=204)
async def revoke_shared_link(
    link_token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    link = await session.get(SharedLink, link_token)
    if link is None or link.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    link.revoked = True
    await session.commit()
    return Response(status_code=204)


@router.get("/api/shared/{link_token}")
async def resolve_shared_link(
    link_token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    link = await session.get(SharedLink, link_token)
    if link is None or link.revoked:
        raise HTTPException(status_code=404, detail="not found")
    exp = link.expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp is not None and exp < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="link expired")
    if link.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="cross-org access denied")
    return {
        "token": link.token,
        "trajectory_id": link.trajectory_id,
        "org_id": link.org_id,
    }
