"""Global run search service.

Extracted from `app.api.runs` to keep the HTTP-adapter layer thin. The public
entry point `list_runs` composes the trajectory filter query: an `agent.env.version`
glob pattern, a `status_tag` filter, and a free-text `q` substring match against
trajectory name/notes/system_prompt/span-attributes.

Queries are preserved verbatim from the pre-split handler — no joins, filters,
ordering, projections, or response shape changed. The pattern parser uses a
shell-glob → SQL ILIKE translation (`*` → `%`, metacharacters escaped).

The route layer delegates Query-param validation (limit bounds etc.) to
FastAPI, so this service assumes inputs are already syntactically valid. The
pattern parser tolerates any string — empty/short patterns simply yield `None`
for unfilled slots, matching pre-split behaviour.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import String, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, AgentVersion, Span, Trajectory
from app.schemas import AgentRunRow, RunsResponse


def glob_to_ilike(glob: str) -> str:
    """Translate a shell-style glob to a SQL ILIKE pattern.

    Escapes ILIKE metacharacters (`%`, `_`, `\\`) so literal text in the glob
    stays literal in SQL, then expands `*` → `%`. `?` and `[…]` are NOT
    treated as glob metacharacters today — only `*` is expanded.
    """
    escaped = glob.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped.replace("*", "%")


def parse_pattern(pattern: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Return (agent_glob, env_glob, version_glob). None = no filter on that slot."""
    segments = pattern.strip().split(".", 2)
    while len(segments) < 3:
        segments.append("*")
    agent, env, version = segments
    return (
        None if agent == "*" else glob_to_ilike(agent),
        None if env == "*" else glob_to_ilike(env),
        None if version == "*" else glob_to_ilike(version),
    )


async def list_runs(
    session: AsyncSession,
    *,
    org_id: str,
    pattern: Optional[str] = None,
    tag: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> RunsResponse:
    stmt = (
        select(Trajectory, Agent.name.label("agent_name"), AgentVersion.label.label("version_label"))
        .outerjoin(Agent, Agent.id == Trajectory.agent_id)
        .outerjoin(AgentVersion, AgentVersion.id == Trajectory.agent_version_id)
        .where(Trajectory.org_id == org_id)
    )

    conditions = []
    if pattern:
        agent_glob, env_glob, version_glob = parse_pattern(pattern)
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
                input_tokens=traj.input_tokens,
                output_tokens=traj.output_tokens,
                status_tag=traj.status_tag,
                name=traj.name,
                environment=traj.environment,
                version_label=version_label,
                agent_name=agent_name,
            )
        )
    return RunsResponse(items=items, total=int(total), limit=limit, offset=offset)
