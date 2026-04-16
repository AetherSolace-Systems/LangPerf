"""OTLP/HTTP receiver — POST /v1/traces.

M2: decode, persist to Postgres, recompute trajectory totals on every insert.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Span, Trajectory
from app.otlp.attrs import derive_kind, extract_token_count
from app.otlp.decoder import decode
from app.otlp.grouping import (
    resolve_environment,
    resolve_service_name,
    resolve_trajectory_id,
    resolve_trajectory_name,
)

logger = logging.getLogger("langperf.otlp")

router = APIRouter()


@router.post("/v1/traces")
async def receive_traces(
    request: Request,
    content_type: str | None = Header(default="application/x-protobuf"),
    session: AsyncSession = Depends(get_session),
):
    body = await request.body()
    try:
        bundles = decode(body, content_type or "application/x-protobuf")
    except Exception as exc:
        logger.exception("failed to decode OTLP body: %s", exc)
        return Response(
            content=json.dumps({"error": str(exc)}),
            status_code=400,
            media_type="application/json",
        )

    span_count = sum(len(b["spans"]) for b in bundles)
    logger.info(
        "received %d span(s) in %d resource-bundle(s) (content-type=%s, bytes=%d)",
        span_count,
        len(bundles),
        content_type,
        len(body),
    )

    touched_trajectories: set[str] = set()
    for bundle in bundles:
        resource_attrs = bundle["resource"]["attrs"]
        for span_dict in bundle["spans"]:
            traj_id = await _upsert_span(session, span_dict, resource_attrs)
            touched_trajectories.add(traj_id)

    # Recompute denormalized totals for every trajectory that received spans.
    for traj_id in touched_trajectories:
        await _recompute_trajectory_totals(session, traj_id)

    await session.commit()

    return Response(content=b"", media_type="application/x-protobuf", status_code=200)


async def _upsert_span(
    session: AsyncSession, span: dict[str, Any], resource_attrs: dict[str, Any]
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

    # Ensure trajectory row exists (create or widen time window).
    await _upsert_trajectory_for_span(
        session,
        traj_id=traj_id,
        trace_id=span["trace_id"],
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
        set_={
            k: stmt.excluded[k]
            for k in span_row
            if k != "span_id"
        },
    )
    await session.execute(stmt)
    return traj_id


async def _upsert_trajectory_for_span(
    session: AsyncSession,
    *,
    traj_id: str,
    trace_id: str,
    resource_attrs: dict[str, Any],
    span: dict[str, Any],
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

    # Do-nothing on conflict on insert; we'll widen the window via UPDATE below.
    stmt = pg_insert(Trajectory).values(**values)
    stmt = stmt.on_conflict_do_nothing(index_elements=[Trajectory.id])
    await session.execute(stmt)

    # For an existing row, widen started_at downward, ended_at upward, and fill
    # in name/environment if they weren't known before.
    existing = await session.get(Trajectory, traj_id)
    if existing:
        changed = False
        if span_started_at < existing.started_at:
            existing.started_at = span_started_at
            changed = True
        if span_ended_at and (existing.ended_at is None or span_ended_at > existing.ended_at):
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


async def _recompute_trajectory_totals(session: AsyncSession, traj_id: str) -> None:
    """Sum step_count, token_count, duration_ms from the span table."""
    result = await session.execute(select(Span).where(Span.trajectory_id == traj_id))
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


def _unix_nano_to_dt(unix_nano: int) -> datetime:
    return datetime.fromtimestamp(unix_nano / 1_000_000_000, tz=timezone.utc)
