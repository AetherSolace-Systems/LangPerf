from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import get_session_by_token
from app.db import get_session
from app.models import User

SESSION_COOKIE = "langperf_session"

Principal = User


async def _resolve_user(db: AsyncSession, token: str | None) -> User | None:
    if not token:
        return None
    sess = await get_session_by_token(db, token)
    if not sess:
        return None
    return await db.get(User, sess.user_id)


def get_current_user():
    async def _dep(
        session: Annotated[AsyncSession, Depends(get_session)],
        token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> User | None:
        return await _resolve_user(session, token)

    return Depends(_dep)


def require_user():
    async def _dep(
        session: Annotated[AsyncSession, Depends(get_session)],
        token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> User:
        user = await _resolve_user(session, token)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        return user

    return Depends(_dep)
