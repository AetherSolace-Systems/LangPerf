"""Agents list / detail / PATCH endpoints."""

from __future__ import annotations

import re
import uuid as _uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.agent_token import generate_token, hash_token
from app.auth.deps import require_user
from app.constants import WINDOW_DELTAS
from app.db import get_session
from app.models import Agent, AgentVersion, Span, Trajectory
from app.otlp.latency_series import latency_series
from app.projects.helpers import get_default_project_id, get_project_by_slug
from app.schemas import (
    AgentDetail,
    AgentMiniMetrics,
    AgentMetrics,
    AgentPatch,
    AgentPromptRow,
    AgentRunRow,
    AgentRunsResponse,
    AgentSummary,
    AgentSummaryWithMetrics,
    AgentToolUsage,
)

router = APIRouter(prefix="/api/agents")

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def _agent_to_dict(agent: Agent) -> dict:
    """Serialize an Agent ORM row to the public summary shape."""
    return AgentSummary.model_validate(agent).model_dump(mode="json")


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    display_name: str | None = None
    description: str | None = None
    language: str | None = None
    github_url: str | None = None
    project_slug: str | None = None


@router.get(
    "",
    response_model=list[AgentSummary] | list[AgentSummaryWithMetrics],
)
async def list_agents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    with_metrics: bool = Query(default=False),
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    project: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
):
    stmt = (
        select(Agent)
        .where(Agent.org_id == user.org_id)
        .order_by(Agent.name)
        .limit(limit)
        .offset(offset)
    )
    if project is not None:
        proj = await get_project_by_slug(session, user.org_id, project)
        if proj is None:
            return []
        stmt = stmt.where(Agent.project_id == proj.id)
    result = await session.execute(stmt)
    agents = list(result.scalars().all())

    if not with_metrics:
        return [AgentSummary.model_validate(a) for a in agents]

    since = datetime.now(tz=timezone.utc) - WINDOW_DELTAS[window]

    runs_by_agent = {
        row.agent_id: int(row.n)
        for row in (
            await session.execute(
                select(Trajectory.agent_id, func.count().label("n"))
                .where(
                    Trajectory.agent_id.is_not(None),
                    Trajectory.started_at >= since,
                    Trajectory.org_id == user.org_id,
                )
                .group_by(Trajectory.agent_id)
            )
        ).all()
    }

    errors_by_agent = {
        row.agent_id: int(row.n)
        for row in (
            await session.execute(
                select(Trajectory.agent_id, func.count().label("n"))
                .where(
                    Trajectory.agent_id.is_not(None),
                    Trajectory.started_at >= since,
                    Trajectory.status_tag == "bad",
                    Trajectory.org_id == user.org_id,
                )
                .group_by(Trajectory.agent_id)
            )
        ).all()
    }

    p95_by_agent = {
        row.agent_id: int(row.p95) if row.p95 is not None else None
        for row in (
            await session.execute(
                select(
                    Trajectory.agent_id,
                    func.percentile_cont(0.95)
                    .within_group(Trajectory.duration_ms.asc())
                    .label("p95"),
                )
                .where(
                    Trajectory.agent_id.is_not(None),
                    Trajectory.started_at >= since,
                    Trajectory.duration_ms.is_not(None),
                    Trajectory.org_id == user.org_id,
                )
                .group_by(Trajectory.agent_id)
            )
        ).all()
    }

    day_bucket = func.date_trunc("day", Trajectory.started_at).label("day")
    spark_rows = (
        await session.execute(
            select(Trajectory.agent_id, day_bucket, func.count().label("n"))
            .where(
                Trajectory.agent_id.is_not(None),
                Trajectory.started_at >= since,
                Trajectory.org_id == user.org_id,
            )
            .group_by(Trajectory.agent_id, "day")
            .order_by(Trajectory.agent_id, "day")
        )
    ).all()
    spark_by_agent: dict[str, list[int]] = {}
    for agent_id, _day, n in spark_rows:
        spark_by_agent.setdefault(agent_id, []).append(int(n))

    version_count_by_agent = {
        row.agent_id: int(row.n)
        for row in (
            await session.execute(
                select(AgentVersion.agent_id, func.count().label("n"))
                .group_by(AgentVersion.agent_id)
            )
        ).all()
    }

    envs_by_agent: dict[str, list[str]] = {}
    env_rows = (
        await session.execute(
            select(Trajectory.agent_id, Trajectory.environment)
            .where(
                Trajectory.agent_id.is_not(None),
                Trajectory.started_at >= since,
                Trajectory.environment.is_not(None),
                Trajectory.org_id == user.org_id,
            )
            .distinct()
        )
    ).all()
    for agent_id, env in env_rows:
        envs_by_agent.setdefault(agent_id, []).append(env)

    out: list[AgentSummaryWithMetrics] = []
    for a in agents:
        runs = runs_by_agent.get(a.id, 0)
        errors = errors_by_agent.get(a.id, 0)
        out.append(
            AgentSummaryWithMetrics(
                **AgentSummary.model_validate(a).model_dump(),
                metrics=AgentMiniMetrics(
                    runs=runs,
                    error_rate=(errors / runs) if runs else 0.0,
                    p95_latency_ms=p95_by_agent.get(a.id),
                ),
                sparkline=spark_by_agent.get(a.id, []),
                version_count=version_count_by_agent.get(a.id, 0),
                environments=sorted(envs_by_agent.get(a.id, [])),
            )
        )
    return out


@router.post("", status_code=201)
async def create_agent(
    payload: AgentCreate,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    existing = (
        await session.execute(
            select(Agent).where(Agent.org_id == user.org_id, Agent.name == payload.name)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"agent {payload.name!r} already exists")
    if payload.project_slug:
        proj = await get_project_by_slug(session, user.org_id, payload.project_slug)
        if proj is None:
            raise HTTPException(
                status_code=404, detail=f"project {payload.project_slug!r} not found"
            )
        project_id = proj.id
    else:
        project_id = await get_default_project_id(session, user.org_id)
    token, prefix = generate_token()
    agent = Agent(
        org_id=user.org_id,
        signature=f"registered:{_uuid.uuid4()}",
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        language=payload.language,
        github_url=payload.github_url,
        token_hash=hash_token(token),
        token_prefix=prefix,
        created_by_user_id=user.id,
        project_id=project_id,
    )
    session.add(agent)
    await session.commit()
    agent = (
        await session.execute(
            select(Agent)
            .where(Agent.id == agent.id)
            .options(selectinload(Agent.project))
        )
    ).scalar_one()
    return {"agent": _agent_to_dict(agent), "token": token}


@router.post("/{name}/rotate-token")
async def rotate_token(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    agent = (
        await session.execute(
            select(Agent).where(Agent.org_id == user.org_id, Agent.name == name)
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    token, prefix = generate_token()
    agent.token_hash = hash_token(token)
    agent.token_prefix = prefix
    agent.last_token_used_at = None
    await session.commit()
    return {"token": token, "token_prefix": prefix}


@router.post("/{name}/issue-token")
async def issue_token(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    agent = (
        await session.execute(
            select(Agent).where(Agent.org_id == user.org_id, Agent.name == name)
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    if agent.token_hash is not None:
        raise HTTPException(status_code=409, detail="agent already has a token; rotate instead")
    token, prefix = generate_token()
    agent.token_hash = hash_token(token)
    agent.token_prefix = prefix
    await session.commit()
    return {"token": token, "token_prefix": prefix}


@router.delete("/{name}", status_code=204)
async def delete_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> None:
    agent = (
        await session.execute(
            select(Agent).where(Agent.org_id == user.org_id, Agent.name == name)
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    await session.delete(agent)
    await session.commit()


@router.get("/{name}", response_model=AgentDetail)
async def get_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentDetail:
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name, Agent.org_id == user.org_id)
        .options(selectinload(Agent.versions), selectinload(Agent.project))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentDetail.model_validate(agent)


@router.patch("/{name}", response_model=AgentDetail)
async def patch_agent(
    name: str,
    patch: AgentPatch,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentDetail:
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name, Agent.org_id == user.org_id)
        .options(selectinload(Agent.versions), selectinload(Agent.project))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")

    if patch.rename_to is not None:
        new_name = patch.rename_to.strip().lower()
        if not NAME_RE.match(new_name):
            raise HTTPException(
                status_code=400,
                detail="name must be lowercase letters/digits/hyphens, 1–64 chars, starting alphanumeric",
            )
        collision = (
            await session.execute(
                select(Agent.id).where(
                    Agent.name == new_name,
                    Agent.id != agent.id,
                    Agent.org_id == user.org_id,
                )
            )
        ).scalar_one_or_none()
        if collision:
            raise HTTPException(status_code=409, detail="name already in use")
        agent.name = new_name

    if patch.display_name is not None:
        agent.display_name = patch.display_name or None
    if patch.description is not None:
        agent.description = patch.description or None
    if patch.owner is not None:
        agent.owner = patch.owner or None
    if patch.github_url is not None:
        agent.github_url = patch.github_url or None
    if patch.project_slug is not None:
        proj = await get_project_by_slug(session, user.org_id, patch.project_slug)
        if proj is None:
            raise HTTPException(status_code=404, detail="project not found")
        agent.project_id = proj.id

    await session.commit()
    agent_id = agent.id
    session.expire(agent)
    agent = (
        await session.execute(
            select(Agent)
            .where(Agent.id == agent_id)
            .options(selectinload(Agent.versions), selectinload(Agent.project))
        )
    ).scalar_one()
    return AgentDetail.model_validate(agent)


async def _resolve_agent(session: AsyncSession, name: str, org_id: str) -> Agent:
    result = await session.execute(
        select(Agent).where(Agent.name == name, Agent.org_id == org_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.get("/{name}/metrics", response_model=AgentMetrics)
async def get_agent_metrics(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentMetrics:
    agent = await _resolve_agent(session, name, user.org_id)
    since = datetime.now(tz=timezone.utc) - WINDOW_DELTAS[window]

    runs = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
                Trajectory.org_id == user.org_id,
            )
        )
    ).scalar_one()

    errors = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
                Trajectory.status_tag == "bad",
                Trajectory.org_id == user.org_id,
            )
        )
    ).scalar_one()

    total_tokens = (
        await session.execute(
            select(func.coalesce(func.sum(Trajectory.token_count), 0)).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
                Trajectory.org_id == user.org_id,
            )
        )
    ).scalar_one()

    p_rows = (
        await session.execute(
            select(
                func.percentile_cont(0.50)
                .within_group(Trajectory.duration_ms.asc())
                .label("p50"),
                func.percentile_cont(0.95)
                .within_group(Trajectory.duration_ms.asc())
                .label("p95"),
                func.percentile_cont(0.99)
                .within_group(Trajectory.duration_ms.asc())
                .label("p99"),
            ).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
                Trajectory.duration_ms.is_not(None),
                Trajectory.org_id == user.org_id,
            )
        )
    ).one()

    def _to_int(x: object) -> Optional[int]:
        if x is None:
            return None
        return int(x)

    latency = await latency_series(session, window=window, agent_id=agent.id)

    return AgentMetrics(
        agent=agent.name,
        window=window,
        runs=int(runs),
        errors=int(errors),
        error_rate=(float(errors) / float(runs)) if runs else 0.0,
        p50_latency_ms=_to_int(p_rows.p50),
        p95_latency_ms=_to_int(p_rows.p95),
        p99_latency_ms=_to_int(p_rows.p99),
        total_tokens=int(total_tokens),
        latency_series=latency,
    )


@router.get("/{name}/tools", response_model=list[AgentToolUsage])
async def get_agent_tools(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[AgentToolUsage]:
    agent = await _resolve_agent(session, name, user.org_id)
    since = datetime.now(tz=timezone.utc) - WINDOW_DELTAS[window]

    result = await session.execute(
        select(
            Span.name.label("tool"),
            func.count().label("calls"),
            func.sum(
                func.cast(Span.status_code == "ERROR", Integer)
            ).label("errors"),
        )
        .join(Trajectory, Trajectory.id == Span.trajectory_id)
        .where(
            Trajectory.agent_id == agent.id,
            Trajectory.started_at >= since,
            Trajectory.org_id == user.org_id,
            Span.kind.in_(("tool", "tool_call")),
        )
        .group_by(Span.name)
        .order_by(func.count().desc())
        .limit(50)
    )
    return [
        AgentToolUsage(
            tool=row.tool,
            calls=int(row.calls),
            errors=int(row.errors or 0),
        )
        for row in result
    ]


@router.get("/{name}/runs", response_model=AgentRunsResponse)
async def get_agent_runs(
    name: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    environment: Optional[str] = Query(default=None),
    version: Optional[str] = Query(default=None, description="version label"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentRunsResponse:
    agent = await _resolve_agent(session, name, user.org_id)

    stmt = (
        select(Trajectory, AgentVersion.label)
        .outerjoin(AgentVersion, AgentVersion.id == Trajectory.agent_version_id)
        .where(Trajectory.agent_id == agent.id, Trajectory.org_id == user.org_id)
    )
    if environment:
        stmt = stmt.where(Trajectory.environment == environment)
    if version:
        stmt = stmt.where(AgentVersion.label == version)

    total = (
        await session.execute(
            select(func.count()).select_from(stmt.order_by(None).subquery())
        )
    ).scalar_one()

    result = await session.execute(
        stmt.order_by(Trajectory.started_at.desc()).limit(limit).offset(offset)
    )
    items: list[AgentRunRow] = []
    for traj, version_label in result.all():
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
            )
        )
    return AgentRunsResponse(items=items, total=int(total), limit=limit, offset=offset)


@router.get("/{name}/prompts", response_model=list[AgentPromptRow])
async def get_agent_prompts(
    name: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[AgentPromptRow]:
    agent = await _resolve_agent(session, name, user.org_id)
    result = await session.execute(
        select(
            Trajectory.system_prompt.label("text"),
            func.count().label("runs"),
            func.min(Trajectory.started_at).label("first_seen_at"),
            func.max(Trajectory.started_at).label("last_seen_at"),
        )
        .where(
            Trajectory.agent_id == agent.id,
            Trajectory.system_prompt.is_not(None),
            Trajectory.org_id == user.org_id,
        )
        .group_by(Trajectory.system_prompt)
        .order_by(func.max(Trajectory.started_at).desc())
        .limit(limit)
    )
    return [
        AgentPromptRow(
            text=row.text,
            runs=int(row.runs),
            first_seen_at=row.first_seen_at,
            last_seen_at=row.last_seen_at,
        )
        for row in result
    ]
