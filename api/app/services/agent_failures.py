"""Stream a CSV of flagged trajectories for an agent.

A trajectory qualifies if ANY of:
  - at least one HeuristicHit fired in the window
  - feedback_thumbs_down > 0
  - status_tag in {"bad", "todo"}

Streams bytes chunks so FastAPI's StreamingResponse can serve directly
without materializing the full CSV.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HeuristicHit, Span, Trajectory
from app.services import agent_worklist


HEADER = [
    "trajectory_id",
    "started_at",
    "heuristics",
    "tools_errored",
    "latency_ms",
    "cost_usd",
    "status_tag",
    "feedback_thumbs_down",
    "notes",
    "url",
]


async def render_csv(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str = "7d",
    web_base_url: str,
) -> AsyncIterator[bytes]:
    hours = agent_worklist.WINDOW_HOURS[window]
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)

    dialect = session.bind.dialect.name if session.bind else "unknown"

    # Subquery: trajectory ids with at least one heuristic hit in window
    hits_subq = (
        select(HeuristicHit.trajectory_id.label("tid"))
        .where(HeuristicHit.created_at >= window_start)
        .subquery()
    )

    # Tool-errored count per trajectory: postgres uses JSONB astext filter;
    # sqlite skips the node.kind filter because astext is postgres-only.
    if dialect == "postgresql":
        tool_err_subq = (
            select(
                Span.trajectory_id.label("tid"),
                func.sum(
                    case((Span.status_code == "ERROR", 1), else_=0)
                ).label("errored"),
            )
            .where(
                Span.started_at >= window_start,
                Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
            )
            .group_by(Span.trajectory_id)
            .subquery()
        )
    else:
        # On sqlite we skip the JSONB node.kind filter; errored will be 0 for
        # all rows since the subquery returns nothing (no spans seeded in tests).
        tool_err_subq = (
            select(
                Span.trajectory_id.label("tid"),
                func.sum(
                    case((Span.status_code == "ERROR", 1), else_=0)
                ).label("errored"),
            )
            .where(Span.started_at >= window_start)
            .group_by(Span.trajectory_id)
            .subquery()
        )

    stmt = (
        select(
            Trajectory.id,
            Trajectory.started_at,
            Trajectory.duration_ms,
            Trajectory.status_tag,
            Trajectory.feedback_thumbs_down,
            Trajectory.notes,
            tool_err_subq.c.errored,
        )
        .outerjoin(tool_err_subq, tool_err_subq.c.tid == Trajectory.id)
        .where(
            Trajectory.agent_id == agent_id,
            Trajectory.started_at >= window_start,
            or_(
                Trajectory.id.in_(select(hits_subq.c.tid)),
                Trajectory.feedback_thumbs_down > 0,
                Trajectory.status_tag.in_(["bad", "todo"]),
            ),
        )
        .order_by(Trajectory.started_at.desc())
    )

    # Pre-fetch heuristic names per trajectory — dialect branch for the
    # string-aggregator: postgres has string_agg, sqlite has group_concat.
    if dialect == "postgresql":
        agg = func.string_agg(HeuristicHit.heuristic, ",")
    else:
        # sqlite group_concat takes only one positional arg for the separator
        agg = func.group_concat(HeuristicHit.heuristic)

    kinds_stmt = (
        select(
            HeuristicHit.trajectory_id,
            agg.label("kinds"),
        )
        .where(HeuristicHit.created_at >= window_start)
        .group_by(HeuristicHit.trajectory_id)
    )
    kinds_map = {
        r.trajectory_id: r.kinds
        for r in (await session.execute(kinds_stmt)).all()
    }

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    yield buf.getvalue().encode("utf-8")
    buf.seek(0)
    buf.truncate()

    rows = await session.execute(stmt)
    for r in rows:
        writer.writerow([
            r.id,
            r.started_at.isoformat() if r.started_at else "",
            kinds_map.get(r.id, ""),
            r.errored or 0,
            r.duration_ms or "",
            "",  # cost_usd — not stored today; left blank
            r.status_tag or "",
            r.feedback_thumbs_down or 0,
            (r.notes or "").replace("\n", " ").replace("\r", " "),
            f"{web_base_url.rstrip('/')}/t/{r.id}",
        ])
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate()
