"""Time-bucketed latency percentiles.

Buckets adapt to the window so each series has a reasonable point count:
    24h  → 1-hour buckets  (24 points)
    7d   → 1-day buckets   (7 points)
    30d  → 1-day buckets   (30 points)

Empty buckets are back-filled with None percentiles so the UI can render
a gap rather than connecting across missing data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import WINDOW_DELTAS
from app.models import Trajectory
from app.schemas import LatencyPoint

_BUCKET_FOR_WINDOW = {
    "24h": ("hour", timedelta(hours=1), 24),
    "7d": ("day", timedelta(days=1), 7),
    "30d": ("day", timedelta(days=1), 30),
}


async def latency_series(
    session: AsyncSession,
    *,
    window: str,
    agent_id: Optional[str] = None,
) -> list[LatencyPoint]:
    """Return a back-filled latency series for the given window + optional agent scope."""
    if window not in WINDOW_DELTAS:
        raise ValueError(f"unknown window: {window}")

    bucket_kind, bucket_delta, bucket_count = _BUCKET_FOR_WINDOW[window]
    now = datetime.now(tz=timezone.utc)
    # Align the last bucket to the current bucket start (truncated).
    if bucket_kind == "hour":
        last_bucket_start = now.replace(minute=0, second=0, microsecond=0)
    else:
        last_bucket_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    first_bucket_start = last_bucket_start - bucket_delta * (bucket_count - 1)

    bucket_col = func.date_trunc(bucket_kind, Trajectory.started_at).label("bucket")

    stmt = (
        select(
            bucket_col,
            func.count().label("runs"),
            func.percentile_cont(0.50)
            .within_group(Trajectory.duration_ms.asc())
            .label("p50"),
            func.percentile_cont(0.95)
            .within_group(Trajectory.duration_ms.asc())
            .label("p95"),
            func.percentile_cont(0.99)
            .within_group(Trajectory.duration_ms.asc())
            .label("p99"),
        )
        .where(
            Trajectory.started_at >= first_bucket_start,
            Trajectory.duration_ms.is_not(None),
        )
        .group_by("bucket")
        .order_by("bucket")
    )
    if agent_id is not None:
        stmt = stmt.where(Trajectory.agent_id == agent_id)

    rows = (await session.execute(stmt)).all()

    def to_int(v: object) -> Optional[int]:
        return None if v is None else int(v)

    seen: dict[datetime, LatencyPoint] = {}
    for bucket, runs, p50, p95, p99 in rows:
        seen[bucket] = LatencyPoint(
            bucket_start=bucket,
            runs=int(runs),
            p50_latency_ms=to_int(p50),
            p95_latency_ms=to_int(p95),
            p99_latency_ms=to_int(p99),
        )

    series: list[LatencyPoint] = []
    cursor = first_bucket_start
    for _ in range(bucket_count):
        if cursor in seen:
            series.append(seen[cursor])
        else:
            series.append(
                LatencyPoint(
                    bucket_start=cursor,
                    runs=0,
                    p50_latency_ms=None,
                    p95_latency_ms=None,
                    p99_latency_ms=None,
                )
            )
        cursor += bucket_delta
    return series
