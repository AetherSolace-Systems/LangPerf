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
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import (
    ALLOWED_TAGS,
    ATTR_COMPLETED,
    ATTR_NODE_KIND,
    ATTR_NOTES,
    ATTR_STATUS_TAG,
)
from app.models import Agent, Span, Trajectory
from app.otlp.agent_resolver import resolve_agent_and_version
from app.otlp.attrs import (
    derive_kind,
    extract_input_tokens,
    extract_output_tokens,
    extract_token_count,
)
from app.otlp.decoder import DecodedBundle, DecodedSpan
from app.otlp.grouping import (
    resolve_environment,
    resolve_service_name,
    resolve_trajectory_id,
    resolve_trajectory_name,
)

logger = logging.getLogger("langperf.otlp.ingest")


async def ingest_bundles(
    session: AsyncSession,
    bundles: list[DecodedBundle],
    *,
    org_id: str,
    agent: Agent,
) -> set[str]:
    """Upsert every span in every bundle; return the set of trajectory UUIDs touched.

    `agent` is the bearer-token-authorized agent — every trajectory
    written here is bound to it. Does NOT commit. Caller batches this
    with recompute_totals, then commits.
    """
    touched: set[str] = set()
    for bundle in bundles:
        resource_attrs = bundle["resource"]["attrs"]
        for span in bundle["spans"]:
            traj_id = await _upsert_span(
                session, span, resource_attrs, org_id=org_id, agent=agent
            )
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
    session: AsyncSession,
    span: DecodedSpan,
    resource_attrs: dict[str, Any],
    *,
    org_id: str,
    agent: Agent,
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
        org_id=org_id,
        agent=agent,
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
    org_id: str,
    agent: Agent,
) -> None:
    # The token-authorized Agent is authoritative for identity *and*
    # display. Previously we trusted the SDK-supplied `service.name`
    # resource attr, which forced callers to keep `agent_name=` in sync
    # with the Agent row in the UI — a footgun with no upside, since the
    # token already told us who this is. Prefer `agent.name`; fall back
    # to the resource attr only for OTel interop paths where no Agent
    # was resolved (should be unreachable today but keeps the shape
    # tolerant).
    service_name = agent.name if agent is not None else resolve_service_name(resource_attrs)
    environment = resolve_environment(resource_attrs)
    name = resolve_trajectory_name(span, resource_attrs)
    agent_id, agent_version_id = await resolve_agent_and_version(
        session, resource_attrs, agent=agent
    )

    values: dict[str, Any] = {
        "id": traj_id,
        "org_id": org_id,
        "trace_id": trace_id,
        "service_name": service_name,
        "environment": environment,
        "name": name,
        "started_at": span_started_at,
        "ended_at": span_ended_at,
        "step_count": 0,
        "token_count": 0,
        "duration_ms": None,
        "agent_id": agent_id,
        "agent_version_id": agent_version_id,
    }

    stmt = pg_insert(Trajectory).values(**values)
    stmt = stmt.on_conflict_do_nothing(index_elements=[Trajectory.id])
    await session.execute(stmt)

    existing = await session.get(Trajectory, traj_id)
    if existing:
        changed = False
        # sqlite's DATETIME type strips tzinfo on INSERT/SELECT round-trips.
        # Normalize `existing` values back to aware-UTC so the tz-aware
        # `span_started_at` / `span_ended_at` can be compared without
        # TypeError. Postgres stores tz correctly and these are no-ops.
        existing_started = _to_utc(existing.started_at)
        existing_ended = _to_utc(existing.ended_at)
        if span_started_at < existing_started:
            existing.started_at = span_started_at
            changed = True
        if span_ended_at and (
            existing_ended is None or span_ended_at > existing_ended
        ):
            existing.ended_at = span_ended_at
            changed = True
        if name and not existing.name:
            existing.name = name
            changed = True
        if environment and not existing.environment:
            existing.environment = environment
            changed = True
        # service_name is canonical from the Agent row; keep it in sync
        # if the user renames the agent in the UI between ingests.
        if agent is not None and existing.service_name != agent.name:
            existing.service_name = agent.name
            changed = True
        if agent_id and not existing.agent_id:
            existing.agent_id = agent_id
            changed = True
        if agent_version_id and not existing.agent_version_id:
            existing.agent_version_id = agent_version_id
            changed = True
        if _apply_sdk_signals(existing, span):
            changed = True
        if changed:
            session.add(existing)


def _apply_sdk_signals(trajectory: Trajectory, span: DecodedSpan) -> bool:
    """Copy SDK-side `mark()` signals off the trajectory-root span into
    the Trajectory row so UI filters reflect them.

    We only read signals off the root span (the one stamped with
    ``langperf.node.kind = "trajectory"`` by the SDK). Other spans
    shouldn't carry these attrs but we'd ignore them if they did — keeps
    intent local to where users actually write the signal.

    Returns True iff any column on `trajectory` changed.
    """
    attrs = span.get("attributes") or {}
    if attrs.get(ATTR_NODE_KIND) != "trajectory":
        return False

    changed = False
    tag = attrs.get(ATTR_STATUS_TAG)
    if isinstance(tag, str) and tag in ALLOWED_TAGS and trajectory.status_tag != tag:
        trajectory.status_tag = tag
        changed = True

    notes = attrs.get(ATTR_NOTES)
    if isinstance(notes, str) and notes and trajectory.notes != notes:
        trajectory.notes = notes
        changed = True

    completed = attrs.get(ATTR_COMPLETED)
    if isinstance(completed, bool) and trajectory.completed != completed:
        trajectory.completed = completed
        changed = True

    return changed


async def _recompute_single(session: AsyncSession, traj_id: str) -> None:
    result = await session.execute(
        select(Span).where(Span.trajectory_id == traj_id)
    )
    spans = list(result.scalars().all())
    step_count = len(spans)
    token_count = sum(extract_token_count(s.attributes) for s in spans)
    input_tokens = sum(
        extract_input_tokens(s.attributes) for s in spans if (s.kind or "").lower() == "llm"
    )
    output_tokens = sum(
        extract_output_tokens(s.attributes) for s in spans if (s.kind or "").lower() == "llm"
    )

    traj = await session.get(Trajectory, traj_id)
    if traj is None:
        return
    traj.step_count = step_count
    traj.token_count = token_count
    traj.input_tokens = input_tokens
    traj.output_tokens = output_tokens
    if traj.started_at and traj.ended_at:
        traj.duration_ms = int(
            (traj.ended_at - traj.started_at).total_seconds() * 1000
        )
    if not traj.system_prompt:
        traj.system_prompt = _extract_system_prompt(spans)
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


def _to_utc(dt: datetime | None) -> datetime | None:
    """Coerce a (possibly naive) datetime to aware-UTC.

    Sqlite's DATETIME type strips tzinfo. Postgres preserves it. The
    ingest comparisons below need both sides to be aware-or-both-naive,
    so normalize on read and treat naive values as already-UTC (which
    they are, since the SDK only ever writes UTC).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


_MAX_PROMPT_LEN = 16_384


def _extract_system_prompt(spans: list[Span]) -> Optional[str]:
    """Return the system prompt from the earliest LLM span that carries one.

    OpenInference flattens messages into `llm.input_messages.<i>.message.role`
    and `.content`. The system message is conventionally index 0, but some
    frameworks put it elsewhere — scan all indices up to 8 to be safe.
    """
    llm_spans = [s for s in spans if (s.kind or "").lower() == "llm"]
    llm_spans.sort(key=lambda s: s.started_at)
    for span in llm_spans:
        attrs = span.attributes or {}
        for i in range(8):
            role = attrs.get(f"llm.input_messages.{i}.message.role")
            if role == "system":
                content = attrs.get(f"llm.input_messages.{i}.message.content")
                if isinstance(content, str) and content.strip():
                    return content[:_MAX_PROMPT_LEN]
                break
    return None
