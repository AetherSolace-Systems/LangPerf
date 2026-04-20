"""Projects service layer.

Extracted from `app.api.projects` to keep the HTTP-adapter layer thin. Every
function here takes an `AsyncSession` plus keyword args and returns the public
project DTO (dict) or `None`. The functions raise `HTTPException` directly —
mirroring the behaviour of the inline code they replaced — so the route
handlers can stay thin.

Note: this module is intentionally separate from `app.projects.helpers`, which
holds lower-level DB primitives (slug normalization, default-project resolver)
shared across many callers. `services/projects.py` is route-facing.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Project
from app.projects.helpers import get_project_by_slug, slugify


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, max_length=255, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=32)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = Field(default=None, max_length=32)
    rename_to_slug: Optional[str] = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")


def project_to_dict(project: Project, agent_count: Optional[int] = None) -> dict:
    d = {
        "id": str(project.id),
        "slug": project.slug,
        "name": project.name,
        "description": project.description,
        "color": project.color,
        "created_at": project.created_at.isoformat() if project.created_at else None,
    }
    if agent_count is not None:
        d["agent_count"] = agent_count
    return d


async def list_projects(session: AsyncSession, *, org_id: str) -> list[dict]:
    rows = (
        await session.execute(
            select(Project, func.count(Agent.id))
            .outerjoin(Agent, Agent.project_id == Project.id)
            .where(Project.org_id == org_id)
            .group_by(Project.id)
            .order_by(Project.slug)
        )
    ).all()
    return [project_to_dict(p, count) for p, count in rows]


async def create_project(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    payload: ProjectCreate,
) -> dict:
    slug = payload.slug or slugify(payload.name)
    existing = await get_project_by_slug(session, org_id, slug)
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"project {slug!r} already exists")
    p = Project(
        id=str(_uuid.uuid4()),
        org_id=org_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        color=payload.color,
        created_by_user_id=user_id,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return project_to_dict(p, 0)


async def get_project(session: AsyncSession, *, org_id: str, slug: str) -> dict:
    p = await get_project_by_slug(session, org_id, slug)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    count = (
        await session.execute(
            select(func.count(Agent.id)).where(Agent.project_id == p.id)
        )
    ).scalar_one()
    return project_to_dict(p, count)


async def update_project(
    session: AsyncSession,
    *,
    org_id: str,
    slug: str,
    payload: ProjectUpdate,
) -> dict:
    p = await get_project_by_slug(session, org_id, slug)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    if payload.name is not None:
        p.name = payload.name
    if payload.description is not None:
        p.description = payload.description
    if payload.color is not None:
        p.color = payload.color
    if payload.rename_to_slug is not None and payload.rename_to_slug != p.slug:
        conflict = await get_project_by_slug(session, org_id, payload.rename_to_slug)
        if conflict is not None:
            raise HTTPException(status_code=409, detail="target slug in use")
        p.slug = payload.rename_to_slug
    await session.commit()
    await session.refresh(p)
    return project_to_dict(p)


async def delete_project(session: AsyncSession, *, org_id: str, slug: str) -> None:
    if slug == "default":
        raise HTTPException(status_code=409, detail="the default project cannot be deleted")
    p = await get_project_by_slug(session, org_id, slug)
    if p is None:
        raise HTTPException(status_code=404, detail="project not found")
    agent_count = (
        await session.execute(
            select(func.count(Agent.id)).where(Agent.project_id == p.id)
        )
    ).scalar_one()
    if agent_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"reassign the {agent_count} agent(s) in this project before deleting",
        )
    await session.delete(p)
    await session.commit()
