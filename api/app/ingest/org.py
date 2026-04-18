"""Helpers for resolving organization context during OTLP ingestion."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization
from sqlalchemy import select


async def get_default_org_id(db: AsyncSession) -> str:
    """Return the ID of the default org, creating it if it doesn't exist."""
    result = await db.execute(select(Organization).where(Organization.slug == "default"))
    org = result.scalar_one_or_none()
    if org is None:
        org = Organization(id=str(uuid4()), name="default", slug="default")
        db.add(org)
        await db.flush()
    return org.id
