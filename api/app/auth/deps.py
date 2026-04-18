from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.mode import DEFAULT_SINGLE_USER, SyntheticUser, is_single_user_mode
from app.auth.session import get_session_by_token
from app.db import get_session
from app.models import User

SESSION_COOKIE = "langperf_session"

Principal = User | SyntheticUser


async def _resolve_user(db: AsyncSession, token: str | None) -> Principal | None:
    if token:
        sess = await get_session_by_token(db, token)
        if sess:
            user = await db.get(User, sess.user_id)
            if user:
                return user
    if await is_single_user_mode(db):
        return DEFAULT_SINGLE_USER
    return None


def get_current_user():
    async def _dep(
        session: Annotated[AsyncSession, Depends(get_session)],
        token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Principal | None:
        return await _resolve_user(session, token)

    return Depends(_dep)


def require_user():
    async def _dep(
        session: Annotated[AsyncSession, Depends(get_session)],
        token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Principal:
        user = await _resolve_user(session, token)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        return user

    return Depends(_dep)
