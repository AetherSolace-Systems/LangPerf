"""`GET /api/runs` — global run search with fuzzy agent.env.version pattern.

The pattern is split on `.` into at most three segments: agent, environment,
version. Each segment is a shell-style glob (`*` matches any char sequence,
literal otherwise). Missing trailing segments default to `*`.

Examples
--------
    support-*.prod.*       → support-* agents in prod, any version
    triage-router.*.v2.*   → triage-router in any env, version labels starting v2.
    *.test.*               → all agents in env "test"
    v1.4.*                 → matches against the agent slot; usually not what
                              you want. Use "*.*.v1.4.*" to filter by version.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent, AgentVersion, Span, Trajectory
from app.schemas import AgentRunRow, RunsResponse

router = APIRouter(prefix="/api/runs")


def _glob_to_ilike(glob: str) -> str:
    # Escape SQL ILIKE metacharacters, then expand `*` to `%`.
    escaped = glob.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped.replace("*", "%")


def _parse_pattern(pattern: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (agent_glob, env_glob, version_glob). None = no filter on that slot."""
    segments = pattern.strip().split(".", 2)
    while len(segments) < 3:
        segments.append("*")
    agent, env, version = segments
    return (
        None if agent == "*" else _glob_to_ilike(agent),
        None if env == "*" else _glob_to_ilike(env),
        None if version == "*" else _glob_to_ilike(version),
    )


@router.get("", response_model=RunsResponse)
async def list_runs(
    pattern: Optional[str] = Query(default=None, description="agent.env.version glob"),
    tag: Optional[str] = Query(default=None, description="good|bad|interesting|todo|none"),
    q: Optional[str] = Query(default=None, description="free-text search"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> RunsResponse:
    stmt = (
        select(Trajectory, Agent.name.label("agent_name"), AgentVersion.label.label("version_label"))
        .outerjoin(Agent, Agent.id == Trajectory.agent_id)
        .outerjoin(AgentVersion, AgentVersion.id == Trajectory.agent_version_id)
    )

    conditions = []
    if pattern:
        agent_glob, env_glob, version_glob = _parse_pattern(pattern)
        if agent_glob is not None:
            conditions.append(Agent.name.ilike(agent_glob))
        if env_glob is not None:
            conditions.append(Trajectory.environment.ilike(env_glob))
        if version_glob is not None:
            conditions.append(AgentVersion.label.ilike(version_glob))

    if tag == "none":
        conditions.append(Trajectory.status_tag.is_(None))
    elif tag:
        conditions.append(Trajectory.status_tag == tag)

    if q:
        like = f"%{q}%"
        span_match = (
            select(Span.trajectory_id)
            .where(cast(Span.attributes, String).ilike(like))
            .distinct()
        )
        conditions.append(
            or_(
                Trajectory.name.ilike(like),
                Trajectory.notes.ilike(like),
                Trajectory.system_prompt.ilike(like),
                Trajectory.id.in_(span_match),
            )
        )

    if conditions:
        stmt = stmt.where(and_(*conditions))

    total = (
        await session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
    ).scalar_one()

    result = await session.execute(
        stmt.order_by(Trajectory.started_at.desc()).limit(limit).offset(offset)
    )
    items: list[AgentRunRow] = []
    for traj, agent_name, version_label in result.all():
        items.append(
            AgentRunRow(
                id=traj.id,
                started_at=traj.started_at,
                ended_at=traj.ended_at,
                duration_ms=traj.duration_ms,
                step_count=traj.step_count,
                token_count=traj.token_count,
                status_tag=traj.status_tag,
                name=traj.name,
                environment=traj.environment,
                version_label=version_label,
                agent_name=agent_name,
            )
        )
    return RunsResponse(items=items, total=int(total), limit=limit, offset=offset)
