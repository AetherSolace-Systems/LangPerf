"""Given OTel resource attributes + a pre-authorized agent, return
(agent_id, agent_version_id) for the trajectory write.

The agent is now determined by the bearer token on the ingest request —
`resolve_agent_and_version` no longer auto-creates agents from
`service.name`/signature. Versions, however, are still resource-attr
driven: each unique `(agent_id, git_sha, package_version)` tuple gets
its own `AgentVersion` row.

Also refreshes `agents.language` / `agents.github_url` if they were not
previously populated — the SDK may discover these post-registration and
it's cheap to keep them current.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    ATTR_AGENT_GIT_ORIGIN,
    ATTR_AGENT_LANGUAGE,
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
    session: AsyncSession,
    resource_attrs: dict[str, Any],
    *,
    agent: Agent,
) -> tuple[str, Optional[str]]:
    """Return (agent_id, agent_version_id) for the resource attrs.

    The agent is authoritative — it was authorized via bearer token in
    the receiver. The only thing we look up from the resource attrs here
    is the `AgentVersion` row (keyed on `git_sha` + `package_version`).

    If no version-identifying attributes are present, returns
    (agent.id, None); the caller leaves `agent_version_id` null on the
    trajectory.
    """
    language = resource_attrs.get(ATTR_AGENT_LANGUAGE)
    git_origin = resource_attrs.get(ATTR_AGENT_GIT_ORIGIN)
    _refresh_agent_metadata(session, agent, language=language, git_origin=git_origin)

    git_sha = resource_attrs.get(ATTR_AGENT_VERSION_SHA)
    short_sha = resource_attrs.get(ATTR_AGENT_VERSION_SHORT_SHA)
    # Fall back to OTel semconv `service.version` when the custom
    # langperf attribute isn't set — this makes the SDK's version=
    # kwarg (Task 6) show up in AgentVersion rows.
    package_version = resource_attrs.get(ATTR_AGENT_VERSION_PACKAGE) or resource_attrs.get("service.version")

    if not any((git_sha, short_sha, package_version)):
        # No version attributes — skip version tracking for this trace.
        return agent.id, None

    version = await _upsert_version(
        session,
        agent_id=agent.id,
        git_sha=git_sha,
        short_sha=short_sha,
        package_version=package_version,
    )
    return agent.id, version.id


def _refresh_agent_metadata(
    session: AsyncSession,
    agent: Agent,
    *,
    language: Optional[str],
    git_origin: Optional[str],
) -> None:
    changed = False
    if language and not agent.language:
        agent.language = language
        changed = True
    inferred_github = _derive_github_url(git_origin)
    if inferred_github and not agent.github_url:
        agent.github_url = inferred_github
        changed = True
    if changed:
        session.add(agent)


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
