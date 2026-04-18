from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def _to_dto(n: Notification) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "payload": n.payload,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat(),
    }


@router.get("")
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
    unread_only: bool = False,
    limit: int = 50,
):
    q = (
        select(Notification)
        .where(Notification.user_id == user.id, Notification.org_id == user.org_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    result = await session.execute(q)
    return [_to_dto(n) for n in result.scalars().all()]


@router.post("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    n = await session.get(Notification, notification_id)
    if n is None or n.user_id != user.id or n.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        await session.commit()
    return Response(status_code=204)


@router.post("/read-all", status_code=204)
async def mark_all_read(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    result = await session.execute(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.org_id == user.org_id,
            Notification.read_at.is_(None),
        )
    )
    now = datetime.now(timezone.utc)
    for n in result.scalars().all():
        n.read_at = now
    await session.commit()
    return Response(status_code=204)
