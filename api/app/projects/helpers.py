"""Project helpers: default-project resolver + slug normalization."""

from __future__ import annotations

import re
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project


_slug_pat = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    s = _slug_pat.sub("-", name.strip().lower()).strip("-")
    return s or "project"


async def get_default_project_id(db: AsyncSession, org_id: str) -> str:
    row = (
        await db.execute(
            select(Project).where(Project.org_id == org_id, Project.slug == "default")
        )
    ).scalar_one_or_none()
    if row is None:
        row = Project(id=str(uuid.uuid4()), org_id=org_id, name="Default", slug="default")
        db.add(row)
        await db.flush()
    return row.id


async def get_project_by_slug(
    db: AsyncSession, org_id: str, slug: str
) -> Optional[Project]:
    return (
        await db.execute(
            select(Project).where(Project.org_id == org_id, Project.slug == slug)
        )
    ).scalar_one_or_none()
