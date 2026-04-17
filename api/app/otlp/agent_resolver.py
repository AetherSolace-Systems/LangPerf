"""Given OTel resource attributes, return (agent_id, agent_version_id).

Upserts rows in agents + agent_versions as needed. Reuses `agents.signature`
as the dedup key, and `(agent_id, git_sha, package_version)` as the version
dedup key. All writes stay in the caller's session; caller commits.

Also updates `agents.language`, `agents.github_url`, and
`agent_versions.last_seen_at` on every ingest so they stay current without
a separate heartbeat.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_naming import generate_name
from app.constants import (
    ATTR_AGENT_GIT_ORIGIN,
    ATTR_AGENT_LANGUAGE,
    ATTR_AGENT_SIGNATURE,
    ATTR_AGENT_VERSION_PACKAGE,
    ATTR_AGENT_VERSION_SHA,
    ATTR_AGENT_VERSION_SHORT_SHA,
)
from app.models import Agent, AgentVersion

logger = logging.getLogger("langperf.otlp.agent_resolver")


def _derive_github_url(git_origin: Optional[str]) -> Optional[str]:
    """Convert `git@github.com:user/repo.git` or ssh URLs into an https github.com URL."""
    if not git_origin:
        return None
    if git_origin.startswith("https://github.com/"):
        return git_origin.removesuffix(".git")
    if git_origin.startswith("git@github.com:"):
        path = git_origin[len("git@github.com:") :].removesuffix(".git")
        return f"https://github.com/{path}"
    return None


def _version_label(package_version: Optional[str], short_sha: Optional[str]) -> str:
    if package_version:
        return package_version
    if short_sha:
        return f"sha:{short_sha}"
    return "unknown"


async def resolve_agent_and_version(
    session: AsyncSession, resource_attrs: dict[str, Any]
) -> tuple[Optional[str], Optional[str]]:
    """Return (agent_id, agent_version_id) for the resource attrs.

    If no signature is present (e.g. legacy SDK), returns (None, None) —
    caller is expected to leave trajectory FKs null, and the backfill step
    will attribute them later.
    """
    signature = resource_attrs.get(ATTR_AGENT_SIGNATURE)
    if not signature:
        return None, None

    git_sha = resource_attrs.get(ATTR_AGENT_VERSION_SHA)
    short_sha = resource_attrs.get(ATTR_AGENT_VERSION_SHORT_SHA)
    package_version = resource_attrs.get(ATTR_AGENT_VERSION_PACKAGE)
    language = resource_attrs.get(ATTR_AGENT_LANGUAGE)
    git_origin = resource_attrs.get(ATTR_AGENT_GIT_ORIGIN)

    agent = await _upsert_agent(
        session,
        signature=signature,
        language=language,
        git_origin=git_origin,
    )
    version = await _upsert_version(
        session,
        agent_id=agent.id,
        git_sha=git_sha,
        short_sha=short_sha,
        package_version=package_version,
    )
    return agent.id, version.id


async def _upsert_agent(
    session: AsyncSession,
    *,
    signature: str,
    language: Optional[str],
    git_origin: Optional[str],
) -> Agent:
    existing = (
        await session.execute(select(Agent).where(Agent.signature == signature))
    ).scalar_one_or_none()
    if existing:
        changed = False
        if language and not existing.language:
            existing.language = language
            changed = True
        inferred_github = _derive_github_url(git_origin)
        if inferred_github and not existing.github_url:
            existing.github_url = inferred_github
            changed = True
        if changed:
            session.add(existing)
        return existing

    name = await _pick_unused_name(session)
    new = Agent(
        id=str(uuid.uuid4()),
        signature=signature,
        name=name,
        language=language,
        github_url=_derive_github_url(git_origin),
    )
    session.add(new)
    await session.flush()
    logger.info("agent_signature_new sig=%s generated_name=%s", signature, name)
    return new


async def _pick_unused_name(session: AsyncSession) -> str:
    taken = set(
        (await session.execute(select(Agent.name))).scalars().all()
    )
    return generate_name(lambda candidate: candidate in taken)


async def _upsert_version(
    session: AsyncSession,
    *,
    agent_id: str,
    git_sha: Optional[str],
    short_sha: Optional[str],
    package_version: Optional[str],
) -> AgentVersion:
    label = _version_label(package_version, short_sha)

    # Build the lookup predicate with explicit IS NULL checks because
    # `column = NULL` is always false in Postgres.
    sha_pred = (
        AgentVersion.git_sha.is_(None) if git_sha is None else AgentVersion.git_sha == git_sha
    )
    pkg_pred = (
        AgentVersion.package_version.is_(None)
        if package_version is None
        else AgentVersion.package_version == package_version
    )
    existing_stmt = select(AgentVersion).where(
        AgentVersion.agent_id == agent_id,
        sha_pred,
        pkg_pred,
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        # onupdate=func.now() on last_seen_at fires whenever the row is UPDATEd.
        # Nudge the row so the update fires (label is idempotent).
        existing.label = label
        session.add(existing)
        return existing

    new = AgentVersion(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        git_sha=git_sha,
        short_sha=short_sha,
        package_version=package_version,
        label=label,
    )
    session.add(new)
    await session.flush()
    return new
