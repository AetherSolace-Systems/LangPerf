"""Persist decoded OTLP bundles into Postgres.

Pure DB-side functions — no HTTP, no FastAPI. The HTTP receiver in
`receiver.py` is a thin shell that decodes the request and delegates to
`ingest_bundles`; everything that touches `AsyncSession` lives here so it
can be unit-tested with an in-memory SQLAlchemy session or exercised from
scripts without spinning up the web server.

Contract:

    await ingest_bundles(session, bundles) -> set[str]   # touched trajectory UUIDs
    await recompute_totals(session, trajectory_ids)      # step/token/duration sums

The caller is responsible for `await session.commit()` after both calls
return — we keep all writes within a single transaction so partial-ingest
doesn't leave trajectory totals out of sync with the spans they summarize.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Span, Trajectory
from app.otlp.attrs import derive_kind, extract_token_count
from app.otlp.decoder import DecodedBundle, DecodedSpan
from app.otlp.grouping import (
    resolve_environment,
    resolve_service_name,
    resolve_trajectory_id,
    resolve_trajectory_name,
)

logger = logging.getLogger("langperf.otlp.ingest")


async def ingest_bundles(
    session: AsyncSession, bundles: list[DecodedBundle]
) -> set[str]:
    """Upsert every span in every bundle; return the set of trajectory UUIDs touched.

    Does NOT commit. Caller batches this with recompute_totals, then commits.
    """
    touched: set[str] = set()
    for bundle in bundles:
        resource_attrs = bundle["resource"]["attrs"]
        for span in bundle["spans"]:
            traj_id = await _upsert_span(session, span, resource_attrs)
            touched.add(traj_id)
    logger.debug("ingested %d bundles; touched %d trajectories", len(bundles), len(touched))
    return touched


async def recompute_totals(
    session: AsyncSession, trajectory_ids: Iterable[str]
) -> None:
    """Re-derive step_count / token_count / duration_ms for each trajectory
    by summing over its spans. Does NOT commit."""
    for traj_id in trajectory_ids:
        await _recompute_single(session, traj_id)


# ── internals ─────────────────────────────────────────────────────────────


async def _upsert_span(
    session: AsyncSession, span: DecodedSpan, resource_attrs: dict[str, Any]
) -> str:
    traj_id = resolve_trajectory_id(span)
    started_at = _unix_nano_to_dt(span["start_time_unix_nano"])
    ended_at = (
        _unix_nano_to_dt(span["end_time_unix_nano"])
        if span["end_time_unix_nano"]
        else None
    )
    duration_ms = (
        int((span["end_time_unix_nano"] - span["start_time_unix_nano"]) / 1_000_000)
        if span["end_time_unix_nano"] and span["start_time_unix_nano"]
        else None
    )

    await _upsert_trajectory_for_span(
        session,
        traj_id=traj_id,
        trace_id=span["trace_id"] or "",
        resource_attrs=resource_attrs,
        span=span,
        span_started_at=started_at,
        span_ended_at=ended_at,
    )

    span_row = {
        "span_id": span["span_id"],
        "trace_id": span["trace_id"],
        "trajectory_id": traj_id,
        "parent_span_id": span["parent_span_id"],
        "name": span["name"],
        "kind": derive_kind(span["attributes"], span["name"]),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "attributes": span["attributes"],
        "events": span["events"] or None,
        "status_code": span["status"]["code"],
    }
    stmt = pg_insert(Span).values(**span_row)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Span.span_id],
        set_={k: stmt.excluded[k] for k in span_row if k != "span_id"},
    )
    await session.execute(stmt)
    return traj_id


async def _upsert_trajectory_for_span(
    session: AsyncSession,
    *,
    traj_id: str,
    trace_id: str,
    resource_attrs: dict[str, Any],
    span: DecodedSpan,
    span_started_at: datetime,
    span_ended_at: datetime | None,
) -> None:
    service_name = resolve_service_name(resource_attrs)
    environment = resolve_environment(resource_attrs)
    name = resolve_trajectory_name(span, resource_attrs)

    values: dict[str, Any] = {
        "id": traj_id,
        "trace_id": trace_id,
        "service_name": service_name,
        "environment": environment,
        "name": name,
        "started_at": span_started_at,
        "ended_at": span_ended_at,
        "step_count": 0,
        "token_count": 0,
        "duration_ms": None,
    }

    # Do-nothing on conflict at insert; we widen the window via UPDATE below.
    stmt = pg_insert(Trajectory).values(**values)
    stmt = stmt.on_conflict_do_nothing(index_elements=[Trajectory.id])
    await session.execute(stmt)

    # For an existing row, widen started_at downward, ended_at upward, and
    # fill in name/environment if they weren't known before.
    existing = await session.get(Trajectory, traj_id)
    if existing:
        changed = False
        if span_started_at < existing.started_at:
            existing.started_at = span_started_at
            changed = True
        if span_ended_at and (
            existing.ended_at is None or span_ended_at > existing.ended_at
        ):
            existing.ended_at = span_ended_at
            changed = True
        if name and not existing.name:
            existing.name = name
            changed = True
        if environment and not existing.environment:
            existing.environment = environment
            changed = True
        if changed:
            session.add(existing)


async def _recompute_single(session: AsyncSession, traj_id: str) -> None:
    result = await session.execute(
        select(Span).where(Span.trajectory_id == traj_id)
    )
    spans = list(result.scalars().all())
    step_count = len(spans)
    token_count = sum(extract_token_count(s.attributes) for s in spans)

    traj = await session.get(Trajectory, traj_id)
    if traj is None:
        return
    traj.step_count = step_count
    traj.token_count = token_count
    if traj.started_at and traj.ended_at:
        traj.duration_ms = int(
            (traj.ended_at - traj.started_at).total_seconds() * 1000
        )
    session.add(traj)
    logger.debug(
        "recompute_totals traj=%s steps=%d tokens=%d duration=%sms",
        traj_id,
        step_count,
        token_count,
        traj.duration_ms,
    )


def _unix_nano_to_dt(unix_nano: int) -> datetime:
    return datetime.fromtimestamp(unix_nano / 1_000_000_000, tz=timezone.utc)
