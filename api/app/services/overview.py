"""Dashboard overview aggregation service.

Extracted from `app.api.overview` to keep the HTTP-adapter layer thin. The
public entry point `build_overview` runs the eight aggregations the Dashboard
needs and composes an `OverviewResponse`. Each private helper is one SQL query
(plus any cheap post-processing), so unit tests can stub them individually
later.

Queries are preserved verbatim from the pre-split handler — no joins, filters,
ordering, or projections changed. `HTTPException` is raised directly where the
inline code used to (via FastAPI `Query` validation on the route), matching
the pre-split behaviour.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import WINDOW_DELTAS
from app.models import Agent, Span, Trajectory
from app.otlp.latency_series import latency_series
from app.schemas import (
    EnvSplit,
    FlaggedRun,
    MostRanAgent,
    OverviewKpi,
    OverviewResponse,
    TopTool,
    VolumeDay,
)


def _to_int(x: object) -> Optional[int]:
    return None if x is None else int(x)


async def _compute_kpis(
    session: AsyncSession, *, org_id: str, since: datetime
) -> OverviewKpi:
    runs = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since,
                Trajectory.org_id == org_id,
            )
        )
    ).scalar_one()

    agents = (
        await session.execute(
            select(func.count(func.distinct(Trajectory.agent_id))).where(
                Trajectory.agent_id.is_not(None),
                Trajectory.started_at >= since,
                Trajectory.org_id == org_id,
            )
        )
    ).scalar_one()

    flagged = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since,
                Trajectory.status_tag.is_not(None),
                Trajectory.org_id == org_id,
            )
        )
    ).scalar_one()

    errors = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since,
                Trajectory.status_tag == "bad",
                Trajectory.org_id == org_id,
            )
        )
    ).scalar_one()

    total_tokens = (
        await session.execute(
            select(func.coalesce(func.sum(Trajectory.token_count), 0)).where(
                Trajectory.started_at >= since,
                Trajectory.org_id == org_id,
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
                Trajectory.org_id == org_id,
            )
        )
    ).one()

    return OverviewKpi(
        runs=int(runs),
        agents=int(agents),
        error_rate=(float(errors) / float(runs)) if runs else 0.0,
        p50_latency_ms=_to_int(p_rows.p50),
        p95_latency_ms=_to_int(p_rows.p95),
        p99_latency_ms=_to_int(p_rows.p99),
        flagged=int(flagged),
        total_tokens=int(total_tokens),
    )


async def _volume_by_day(
    session: AsyncSession, *, org_id: str, since: datetime
) -> list[VolumeDay]:
    """Volume is pinned to the last 24h with hourly buckets regardless of the
    outer `window` — the dashboard uses it as an "is anything happening right
    now?" monitor. Empty hours are back-filled so the chart is always 24 bars.

    `since` is accepted for signature symmetry but ignored here by design.
    """
    vol_since = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    hour_bucket = func.date_trunc("hour", Trajectory.started_at).label("hour")
    vol_rows = (
        await session.execute(
            select(
                hour_bucket,
                Trajectory.environment,
                func.count().label("n"),
            )
            .where(
                Trajectory.started_at >= vol_since,
                Trajectory.org_id == org_id,
            )
            .group_by("hour", Trajectory.environment)
            .order_by("hour")
        )
    ).all()

    by_hour: dict[datetime, dict[str, int]] = {}
    for hour, env, n in vol_rows:
        bucket = by_hour.setdefault(hour, {"prod": 0, "staging": 0, "dev": 0, "other": 0})
        key = env if env in ("prod", "staging", "dev") else "other"
        bucket[key] += int(n)

    # Backfill every hour in the 24h window so the chart always has 24 bars.
    now_hour = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)
    volume_by_day: list[VolumeDay] = []
    for i in range(24):
        h = now_hour - timedelta(hours=23 - i)
        b = by_hour.get(h, {"prod": 0, "staging": 0, "dev": 0, "other": 0})
        volume_by_day.append(
            VolumeDay(
                day=h,
                prod=b["prod"],
                staging=b["staging"],
                dev=b["dev"],
                other=b["other"],
            )
        )
    return volume_by_day


async def _env_split(
    session: AsyncSession, *, org_id: str, since: datetime
) -> list[EnvSplit]:
    env_rows = (
        await session.execute(
            select(
                func.coalesce(Trajectory.environment, "—"),
                func.count(),
            )
            .where(
                Trajectory.started_at >= since,
                Trajectory.org_id == org_id,
            )
            .group_by(Trajectory.environment)
            .order_by(func.count().desc())
        )
    ).all()
    return [EnvSplit(environment=e, runs=int(n)) for e, n in env_rows]


async def _top_tools(
    session: AsyncSession, *, org_id: str, since: datetime, limit: int = 10
) -> list[TopTool]:
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
                Trajectory.org_id == org_id,
                Span.kind.in_(("tool", "tool_call")),
            )
            .group_by(Span.name)
            .order_by(func.count().desc())
            .limit(limit)
        )
    ).all()
    return [
        TopTool(tool=row.tool, calls=int(row.calls), errors=int(row.errors or 0))
        for row in tool_rows
    ]


async def _recent_flagged(
    session: AsyncSession, *, org_id: str, since: datetime, limit: int = 10
) -> list[FlaggedRun]:
    flagged_rows = (
        await session.execute(
            select(Trajectory, Agent.name)
            .outerjoin(Agent, Agent.id == Trajectory.agent_id)
            .where(
                Trajectory.started_at >= since,
                Trajectory.status_tag.is_not(None),
                Trajectory.org_id == org_id,
            )
            .order_by(Trajectory.started_at.desc())
            .limit(limit)
        )
    ).all()
    return [
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


async def _heatmap(
    session: AsyncSession, *, org_id: str, since: datetime
) -> list:
    """Deprecated — UI no longer renders the heatmap. Kept for backward
    compat so `OverviewResponse.heatmap` stays `[]` as before the split."""
    return []


async def _most_ran_agents(
    session: AsyncSession, *, org_id: str, since: datetime, limit: int = 10
) -> list[MostRanAgent]:
    most_ran_rows = (
        await session.execute(
            select(
                Agent.name.label("name"),
                func.count().label("runs"),
                func.sum(
                    func.cast(Trajectory.status_tag == "bad", Integer)
                ).label("errors"),
            )
            .join(Trajectory, Trajectory.agent_id == Agent.id)
            .where(
                Trajectory.started_at >= since,
                Trajectory.org_id == org_id,
            )
            .group_by(Agent.name)
            .order_by(func.count().desc())
            .limit(limit)
        )
    ).all()
    return [
        MostRanAgent(
            name=row.name,
            runs=int(row.runs),
            error_rate=(int(row.errors or 0) / int(row.runs)) if int(row.runs) else 0.0,
        )
        for row in most_ran_rows
    ]


async def _latency_series(
    session: AsyncSession, *, org_id: str, window: str
) -> list:
    # `latency_series` helper lives in app.otlp and handles its own bucketing.
    # `org_id` is accepted for signature symmetry; the helper does not scope
    # by org today — matches pre-split behaviour.
    return await latency_series(session, window=window)


async def build_overview(
    session: AsyncSession, *, org_id: str, window: str
) -> OverviewResponse:
    since = datetime.now(tz=timezone.utc) - WINDOW_DELTAS[window]

    kpi = await _compute_kpis(session, org_id=org_id, since=since)
    volume_by_day = await _volume_by_day(session, org_id=org_id, since=since)
    env_split = await _env_split(session, org_id=org_id, since=since)
    top_tools = await _top_tools(session, org_id=org_id, since=since)
    recent_flagged = await _recent_flagged(session, org_id=org_id, since=since)
    heatmap = await _heatmap(session, org_id=org_id, since=since)
    most_ran_agents = await _most_ran_agents(session, org_id=org_id, since=since)
    latency = await _latency_series(session, org_id=org_id, window=window)

    return OverviewResponse(
        window=window,
        kpi=kpi,
        volume_by_day=volume_by_day,
        env_split=env_split,
        top_tools=top_tools,
        recent_flagged=recent_flagged,
        heatmap=heatmap,  # deprecated — UI no longer renders; kept for backward compat
        most_ran_agents=most_ran_agents,
        latency_series=latency,
    )
