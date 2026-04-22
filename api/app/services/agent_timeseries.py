"""Bucketed time-series metrics for an agent's detail page.

Step size derived from window:
    24h -> 5 minute buckets  (288 buckets)
    7d  -> 1 hour buckets    (168 buckets)
    30d -> 6 hour buckets    (120 buckets)

Supported metrics:
    p95_latency, cost_per_1k, tool_success, feedback_down,
    completion_rate, token_efficiency
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Span, Trajectory


WINDOW_CONFIG = {
    "24h": {"hours": 24, "step_ms": 5 * 60 * 1000},
    "7d":  {"hours": 168, "step_ms": 60 * 60 * 1000},
    "30d": {"hours": 720, "step_ms": 6 * 60 * 60 * 1000},
}

SUPPORTED_METRICS = {
    "p95_latency",
    "cost_per_1k",
    "tool_success",
    "feedback_down",
    "completion_rate",
    "token_efficiency",
}


async def compute(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str,
    metrics: Iterable[str],
) -> list[dict[str, Any]]:
    cfg = WINDOW_CONFIG[window]
    now = datetime.now(timezone.utc)
    end = _bucket_floor(now, cfg["step_ms"])
    start = end - timedelta(hours=cfg["hours"])
    bucket_starts = _bucket_range(start, end, cfg["step_ms"])

    out: list[dict[str, Any]] = []
    for metric in metrics:
        if metric not in SUPPORTED_METRICS:
            raise ValueError(f"unsupported metric {metric!r}")
        series = await _compute_metric(
            session,
            agent_id=agent_id,
            metric=metric,
            bucket_starts=bucket_starts,
            step_ms=cfg["step_ms"],
        )
        out.append(
            {
                "metric": metric,
                "window": window,
                "step_ms": cfg["step_ms"],
                "buckets": series,
            }
        )
    return out


def _bucket_floor(ts: datetime, step_ms: int) -> datetime:
    epoch_ms = int(ts.timestamp() * 1000)
    floored_ms = (epoch_ms // step_ms) * step_ms
    return datetime.fromtimestamp(floored_ms / 1000, tz=timezone.utc)


def _bucket_range(start: datetime, end: datetime, step_ms: int) -> list[datetime]:
    step = timedelta(milliseconds=step_ms)
    out, cur = [], start
    while cur < end:
        out.append(cur)
        cur += step
    return out


def _sql_bucket_key(column, step_ms: int):
    """Floor a timestamp column to `step_ms` buckets, return epoch-ms integer.
    Portable across sqlite and postgres: both accept EXTRACT(EPOCH FROM ts).
    CAST to Integer gives floor semantics on both dialects.
    """
    epoch_ms = func.cast(func.extract("epoch", column) * 1000, Integer)
    return func.cast(epoch_ms / step_ms, Integer) * step_ms


async def _compute_metric(
    session: AsyncSession,
    *,
    agent_id: str,
    metric: str,
    bucket_starts: list[datetime],
    step_ms: int,
) -> list[dict[str, Any]]:
    index = {b: i for i, b in enumerate(bucket_starts)}
    buckets = [
        {"ts_ms": int(b.timestamp() * 1000), "value": None, "count": 0}
        for b in bucket_starts
    ]
    start = bucket_starts[0]
    end = bucket_starts[-1] + timedelta(milliseconds=step_ms)

    if metric == "p95_latency":
        rows = await _p95_latency_rows(session, agent_id, start, end, step_ms)
        for ts_ms, p95, count in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and count:
                buckets[i]["value"] = float(p95) if p95 is not None else None
                buckets[i]["count"] = int(count)

    elif metric == "tool_success":
        rows = await _tool_success_rows(session, agent_id, start, end, step_ms)
        for ts_ms, ok, total in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and total:
                buckets[i]["value"] = float(ok) / float(total)
                buckets[i]["count"] = int(total)

    elif metric == "feedback_down":
        rows = await _feedback_down_rows(session, agent_id, start, end, step_ms)
        for ts_ms, n in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None:
                buckets[i]["value"] = int(n)
                buckets[i]["count"] = int(n)

    elif metric == "completion_rate":
        rows = await _completion_rate_rows(session, agent_id, start, end, step_ms)
        for ts_ms, completed, total in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and total:
                buckets[i]["value"] = float(completed) / float(total)
                buckets[i]["count"] = int(total)

    elif metric == "token_efficiency":
        rows = await _token_efficiency_rows(session, agent_id, start, end, step_ms)
        for ts_ms, out_tok, in_tok in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and in_tok:
                buckets[i]["value"] = float(out_tok) / float(in_tok)
                buckets[i]["count"] = int(in_tok)

    elif metric == "cost_per_1k":
        # Cost is not stored per-trajectory today. Return zero-filled
        # skeleton with None values so the client contract is stable.
        pass

    return buckets


def _locate_bucket(ts_ms, index, step_ms):
    bucket_ms = (int(ts_ms) // step_ms) * step_ms
    bucket_dt = datetime.fromtimestamp(bucket_ms / 1000, tz=timezone.utc)
    return index.get(bucket_dt)


async def _p95_latency_rows(session, agent_id, start, end, step_ms):
    # percentile_cont is postgres-only; on sqlite we return no rows so
    # the caller leaves all buckets as None (correct for empty/stub lane).
    dialect = session.bind.dialect.name if session.bind else "unknown"
    if dialect != "postgresql":
        return []

    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    stmt = (
        select(
            bucket_sql.label("bucket_ms"),
            func.percentile_cont(0.95).within_group(Trajectory.duration_ms).label("p95"),
            func.count().label("count"),
        )
        .where(
            Trajectory.agent_id == agent_id,
            Trajectory.started_at >= start,
            Trajectory.started_at < end,
            Trajectory.duration_ms.isnot(None),
        )
        .group_by("bucket_ms")
        .order_by("bucket_ms")
    )
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.p95, r.count) for r in rows]


async def _tool_success_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Span.started_at, step_ms)
    ok_expr = func.sum(
        case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)
    ).label("ok")
    stmt = (
        select(
            bucket_sql.label("bucket_ms"),
            ok_expr,
            func.count().label("total"),
        )
        .join(Trajectory, Trajectory.id == Span.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            Span.started_at >= start,
            Span.started_at < end,
            Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
        )
        .group_by("bucket_ms")
        .order_by("bucket_ms")
    )
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.ok or 0, r.total or 0) for r in rows]


async def _feedback_down_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    stmt = (
        select(
            bucket_sql.label("bucket_ms"),
            func.count().label("n"),
        )
        .where(
            Trajectory.agent_id == agent_id,
            Trajectory.started_at >= start,
            Trajectory.started_at < end,
            Trajectory.feedback_thumbs_down > 0,
        )
        .group_by("bucket_ms")
        .order_by("bucket_ms")
    )
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.n or 0) for r in rows]


async def _completion_rate_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    completed_expr = func.sum(
        case((Trajectory.completed.is_(True), 1), else_=0).cast(Integer)
    ).label("completed")
    total_expr = func.sum(
        case((Trajectory.completed.is_(None), 0), else_=1).cast(Integer)
    ).label("total")
    stmt = (
        select(
            bucket_sql.label("bucket_ms"),
            completed_expr,
            total_expr,
        )
        .where(
            Trajectory.agent_id == agent_id,
            Trajectory.started_at >= start,
            Trajectory.started_at < end,
        )
        .group_by("bucket_ms")
        .order_by("bucket_ms")
    )
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.completed or 0, r.total or 0) for r in rows]


async def _token_efficiency_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    stmt = (
        select(
            bucket_sql.label("bucket_ms"),
            func.sum(Trajectory.output_tokens).label("out_tok"),
            func.sum(Trajectory.input_tokens).label("in_tok"),
        )
        .where(
            Trajectory.agent_id == agent_id,
            Trajectory.started_at >= start,
            Trajectory.started_at < end,
        )
        .group_by("bucket_ms")
        .order_by("bucket_ms")
    )
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.out_tok or 0, r.in_tok or 0) for r in rows]
