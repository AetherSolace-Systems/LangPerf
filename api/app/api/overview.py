"""Dashboard aggregation endpoint — scopes counts, tools, and heatmap
across every agent ingested into this workspace.

Designed to fit on a single HTTP response so the Dashboard is one fetch.
All aggregates bucketed by the `window` query param (24h / 7d / 30d).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent, Span, Trajectory
from app.schemas import (
    EnvSplit,
    FlaggedRun,
    HeatmapCell,
    OverviewKpi,
    OverviewResponse,
    TopTool,
    VolumeDay,
)

router = APIRouter(prefix="/api/overview")

_WINDOW_DELTA = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@router.get("", response_model=OverviewResponse)
async def get_overview(
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
) -> OverviewResponse:
    since = datetime.now(tz=timezone.utc) - _WINDOW_DELTA[window]

    runs = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since
            )
        )
    ).scalar_one()

    agents = (
        await session.execute(
            select(func.count(func.distinct(Trajectory.agent_id))).where(
                Trajectory.agent_id.is_not(None),
                Trajectory.started_at >= since,
            )
        )
    ).scalar_one()

    flagged = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since,
                Trajectory.status_tag.is_not(None),
            )
        )
    ).scalar_one()

    errors = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since,
                Trajectory.status_tag == "bad",
            )
        )
    ).scalar_one()

    total_tokens = (
        await session.execute(
            select(func.coalesce(func.sum(Trajectory.token_count), 0)).where(
                Trajectory.started_at >= since
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
                Trajectory.started_at >= since,
                Trajectory.duration_ms.is_not(None),
            )
        )
    ).one()

    def _to_int(x: object) -> Optional[int]:
        return None if x is None else int(x)

    kpi = OverviewKpi(
        runs=int(runs),
        agents=int(agents),
        error_rate=(float(errors) / float(runs)) if runs else 0.0,
        p50_latency_ms=_to_int(p_rows.p50),
        p95_latency_ms=_to_int(p_rows.p95),
        p99_latency_ms=_to_int(p_rows.p99),
        flagged=int(flagged),
        total_tokens=int(total_tokens),
    )

    day_bucket = func.date_trunc("day", Trajectory.started_at).label("day")
    vol_rows = (
        await session.execute(
            select(
                day_bucket,
                Trajectory.environment,
                func.count().label("n"),
            )
            .where(Trajectory.started_at >= since)
            .group_by("day", Trajectory.environment)
            .order_by("day")
        )
    ).all()

    by_day: dict[datetime, dict[str, int]] = {}
    for day, env, n in vol_rows:
        bucket = by_day.setdefault(day, {"prod": 0, "staging": 0, "dev": 0, "other": 0})
        key = env if env in ("prod", "staging", "dev") else "other"
        bucket[key] += int(n)

    volume_by_day = [
        VolumeDay(
            day=day,
            prod=bucket["prod"],
            staging=bucket["staging"],
            dev=bucket["dev"],
            other=bucket["other"],
        )
        for day, bucket in sorted(by_day.items())
    ]

    env_rows = (
        await session.execute(
            select(
                func.coalesce(Trajectory.environment, "—"),
                func.count(),
            )
            .where(Trajectory.started_at >= since)
            .group_by(Trajectory.environment)
            .order_by(func.count().desc())
        )
    ).all()
    env_split = [EnvSplit(environment=e, runs=int(n)) for e, n in env_rows]

    tool_rows = (
        await session.execute(
            select(
                Span.name.label("tool"),
                func.count().label("calls"),
                func.sum(
                    func.cast(Span.status_code == "ERROR", Integer)
                ).label("errors"),
            )
            .join(Trajectory, Trajectory.id == Span.trajectory_id)
            .where(
                Trajectory.started_at >= since,
                Span.kind.in_(("tool", "tool_call")),
            )
            .group_by(Span.name)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    top_tools = [
        TopTool(tool=row.tool, calls=int(row.calls), errors=int(row.errors or 0))
        for row in tool_rows
    ]

    flagged_rows = (
        await session.execute(
            select(Trajectory, Agent.name)
            .outerjoin(Agent, Agent.id == Trajectory.agent_id)
            .where(
                Trajectory.started_at >= since,
                Trajectory.status_tag.is_not(None),
            )
            .order_by(Trajectory.started_at.desc())
            .limit(10)
        )
    ).all()
    recent_flagged = [
        FlaggedRun(
            id=traj.id,
            started_at=traj.started_at,
            duration_ms=traj.duration_ms,
            status_tag=traj.status_tag,
            agent_name=agent_name,
            summary=traj.name,
        )
        for traj, agent_name in flagged_rows
    ]

    top_agents = (
        await session.execute(
            select(Agent.name, func.count().label("n"))
            .join(Trajectory, Trajectory.agent_id == Agent.id)
            .where(Trajectory.started_at >= since)
            .group_by(Agent.name)
            .order_by(func.count().desc())
            .limit(6)
        )
    ).all()
    agent_names = [row.name for row in top_agents]
    top_tool_names = [t.tool for t in top_tools[:6]]

    if agent_names and top_tool_names:
        hm_rows = (
            await session.execute(
                select(
                    Agent.name.label("agent_name"),
                    Span.name.label("tool"),
                    func.count().label("calls"),
                )
                .join(Trajectory, Trajectory.id == Span.trajectory_id)
                .join(Agent, Agent.id == Trajectory.agent_id)
                .where(
                    Trajectory.started_at >= since,
                    Span.kind.in_(("tool", "tool_call")),
                    Agent.name.in_(agent_names),
                    Span.name.in_(top_tool_names),
                )
                .group_by(Agent.name, Span.name)
            )
        ).all()
        heatmap = [
            HeatmapCell(agent_name=row.agent_name, tool=row.tool, calls=int(row.calls))
            for row in hm_rows
        ]
    else:
        heatmap = []

    return OverviewResponse(
        window=window,
        kpi=kpi,
        volume_by_day=volume_by_day,
        env_split=env_split,
        top_tools=top_tools,
        recent_flagged=recent_flagged,
        heatmap=heatmap,
    )
