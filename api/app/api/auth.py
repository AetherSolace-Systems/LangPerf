import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import SESSION_COOKIE, get_current_user, require_user
from app.auth.mode import is_single_user_mode
from app.auth.password import hash_password, verify_password
from app.auth.session import create_session, delete_session
from app.db import get_session
from app.models import Organization, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_KW = dict(
    key=SESSION_COOKIE,
    httponly=True,
    samesite="lax",
    secure=False,  # set True behind https
    path="/",
)


class SignupPayload(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=255)


class LoginPayload(BaseModel):
    email: str = Field(min_length=1, max_length=320)
    password: str


class UserDto(BaseModel):
    id: str
    org_id: str
    email: str
    display_name: str
    is_admin: bool


def _to_dto(u) -> UserDto:
    return UserDto(
        id=str(u.id),
        org_id=str(u.org_id),
        email=u.email,
        display_name=u.display_name,
        is_admin=u.is_admin,
    )


@router.get("/mode")
async def mode(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    return {"mode": "single_user" if await is_single_user_mode(session) else "multi_user"}


@router.post("/signup", status_code=201)
async def signup(
    payload: SignupPayload,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    existing = await session.execute(select(User).limit(1))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=403, detail="signup closed; ask an admin for an invite")

    org = Organization(id=str(uuid.uuid4()), name="default", slug="default")
    session.add(org)
    await session.flush()
    user = User(
        id=str(uuid.uuid4()),
        org_id=org.id,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_admin=True,
    )
    session.add(user)
    await session.flush()
    sess = await create_session(session, user.id)
    response.set_cookie(value=sess.token, **COOKIE_KW)
    return {"user": _to_dto(user).model_dump()}


@router.post("/login")
async def login(
    payload: LoginPayload,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    sess = await create_session(session, user.id)
    response.set_cookie(value=sess.token, **COOKIE_KW)
    return {"user": _to_dto(user).model_dump()}


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
):
    if token:
        await delete_session(session, token)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return Response(status_code=204)


@router.get("/me")
async def me(user=require_user()):
    return {"user": _to_dto(user).model_dump()}
