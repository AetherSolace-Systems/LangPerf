import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session as SessionModel

SESSION_TTL = timedelta(days=30)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(expires_at: datetime) -> bool:
    now = _now_utc()
    # SQLite returns naive datetimes even when the column is timezone=True.
    # Normalise both sides to aware UTC for a safe comparison.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at < now


async def create_session(db: AsyncSession, user_id: uuid.UUID) -> SessionModel:
    token = secrets.token_urlsafe(32)
    sess = SessionModel(
        token=token,
        user_id=user_id,
        expires_at=_now_utc() + SESSION_TTL,
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def get_session_by_token(db: AsyncSession, token: str) -> SessionModel | None:
    result = await db.execute(select(SessionModel).where(SessionModel.token == token))
    sess = result.scalar_one_or_none()
    if sess is None:
        return None
    if _is_expired(sess.expires_at):
        return None
    return sess


async def delete_session(db: AsyncSession, token: str) -> None:
    result = await db.execute(select(SessionModel).where(SessionModel.token == token))
    sess = result.scalar_one_or_none()
    if sess:
        await db.delete(sess)
        await db.commit()
