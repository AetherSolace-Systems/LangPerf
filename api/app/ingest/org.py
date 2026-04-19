"""Helpers for resolving organization context during OTLP ingestion."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FailureMode, Organization, Project
from sqlalchemy import select


DEFAULT_FAILURE_MODES = [
    ("wrong_tool", "Wrong tool", "warn"),
    ("bad_args", "Bad args", "warn"),
    ("hallucination", "Hallucination", "peach-neon"),
    ("loop", "Loop", "peach-neon"),
    ("misunderstood_intent", "Misunderstood intent", "steel-mist"),
]


async def get_default_org_id(db: AsyncSession) -> str:
    """Return the ID of the default org, creating it + seed data if missing.

    Migration 0010 seeds failure modes for every existing org at migration
    time. Migration 0016 seeds the default project per org at migration time.
    For code paths that create the default org outside a migration
    (tests with create_all, fresh DATABASE_URL without running migrations),
    we seed here so downstream queries see the same defaults.
    """
    result = await db.execute(select(Organization).where(Organization.slug == "default"))
    org = result.scalar_one_or_none()
    if org is None:
        org = Organization(id=str(uuid4()), name="default", slug="default")
        db.add(org)
        await db.flush()
        for slug, label, color in DEFAULT_FAILURE_MODES:
            db.add(FailureMode(org_id=org.id, slug=slug, label=label, color=color))
        await db.flush()
        # Seed the default project (mirrors migration 0016).
        db.add(Project(id=str(uuid4()), org_id=org.id, name="Default", slug="default"))
        await db.flush()
    return org.id
