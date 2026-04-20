"""Project endpoints.

Thin HTTP-adapter layer — all business logic lives in `app.services.projects`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.services import projects as projects_service
from app.services.projects import ProjectCreate, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[dict]:
    return await projects_service.list_projects(session, org_id=user.org_id)


@router.post("", status_code=201)
async def create_project(
    payload: ProjectCreate,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    return await projects_service.create_project(
        session,
        org_id=user.org_id,
        user_id=user.id,
        payload=payload,
    )


@router.get("/{slug}")
async def get_project(
    slug: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    return await projects_service.get_project(session, org_id=user.org_id, slug=slug)


@router.patch("/{slug}")
async def update_project(
    slug: str,
    payload: ProjectUpdate,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    return await projects_service.update_project(
        session,
        org_id=user.org_id,
        slug=slug,
        payload=payload,
    )


@router.delete("/{slug}", status_code=204)
async def delete_project(
    slug: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> None:
    await projects_service.delete_project(session, org_id=user.org_id, slug=slug)
