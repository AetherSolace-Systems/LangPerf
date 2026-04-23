"""Multi-segment (durable/resumable) trajectories — ingest upserts into one Trajectory row.

The SDK's new `id=` + `final=` kwargs enable a single logical run to
emit spans from multiple processes. These tests confirm the ingest path
already handles that shape — no code changes expected, but regressions
here would silently break durable-agent users.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Agent, Organization, Project, Span, Trajectory
from app.otlp.decoder import DecodedBundle, DecodedSpan
from app.otlp.ingest import ingest_bundles


def _ns(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000_000)


def _make_root(
    *,
    trajectory_id: str,
    trace_id: str,
    span_id: str,
    started_at: datetime,
    duration_s: float = 1.0,
    completed: bool | None = None,
    status_tag: str | None = None,
) -> DecodedSpan:
    attrs: dict = {
        "langperf.node.kind": "trajectory",
        "langperf.trajectory.id": trajectory_id,
    }
    if completed is not None:
        attrs["langperf.completed"] = completed
    if status_tag is not None:
        attrs["langperf.status_tag"] = status_tag
    end_ns = _ns(started_at) + int(duration_s * 1_000_000_000)
    return DecodedSpan(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=None,
        name=f"segment-{span_id[:4]}",
        kind="INTERNAL",
        start_time_unix_nano=_ns(started_at),
        end_time_unix_nano=end_ns,
        attributes=attrs,
        events=[],
        status={"code": "UNSET", "message": ""},
        scope={"name": None, "version": None},
    )


async def _seed(session) -> tuple[Organization, Agent]:
    org = Organization(id=str(uuid.uuid4()), name="Acme", slug="acme")
    project = Project(id=str(uuid.uuid4()), org_id=org.id, name="Default", slug="default")
    agent = Agent(
        id=str(uuid.uuid4()),
        org_id=org.id,
        project_id=project.id,
        signature=f"sig-{uuid.uuid4()}",
        name=f"widget-{uuid.uuid4().hex[:8]}",
        language="python",
        token_prefix=f"lp_{uuid.uuid4().hex[:8]}",
        token_hash="x" * 60,
        created_at=datetime.now(timezone.utc),
    )
    session.add_all([org, project, agent])
    await session.commit()
    return org, agent


@pytest.mark.asyncio
async def test_three_segments_roll_up_to_one_trajectory_row(session):
    """Three process segments → one Trajectory row; window spans all three."""
    org, agent = await _seed(session)
    traj_id = str(uuid.uuid4())
    seg1_start = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    seg2_start = seg1_start + timedelta(hours=1)
    seg3_start = seg2_start + timedelta(hours=1)

    # Segment 1 — non-final, no `completed` attribute.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="a" * 32,
                    span_id="1" * 16,
                    started_at=seg1_start,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # Segment 2 — still non-final.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="b" * 32,  # different trace_id — different OTel trace
                    span_id="2" * 16,
                    started_at=seg2_start,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # After segment 2: Trajectory.completed must still be None.
    traj = await session.get(Trajectory, traj_id)
    assert traj is not None
    assert traj.completed is None

    # Segment 3 — final.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="c" * 32,
                    span_id="3" * 16,
                    started_at=seg3_start,
                    completed=True,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # Refresh — one row, window spans all three, completed=True.
    await session.refresh(traj)
    assert traj.completed is True

    # started_at pinned to earliest segment; ended_at to latest.
    # sqlite strips tzinfo on round-trip — compare in UTC.
    def to_utc(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    assert to_utc(traj.started_at) == seg1_start
    assert to_utc(traj.ended_at) == seg3_start + timedelta(seconds=1)

    # Three root spans share one trajectory_id.
    result = await session.execute(
        select(Span).where(Span.trajectory_id == traj_id)
    )
    spans = list(result.scalars().all())
    assert len(spans) == 3
    assert all(s.parent_span_id is None for s in spans)


@pytest.mark.asyncio
async def test_mark_during_resume_last_writer_wins(session):
    """Second segment's mark() overwrites the first's on the Trajectory row."""
    org, agent = await _seed(session)
    traj_id = str(uuid.uuid4())
    t0 = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)

    # Seg 1 marks "bad".
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="a" * 32,
                    span_id="1" * 16,
                    started_at=t0,
                    status_tag="bad",
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()
    traj = await session.get(Trajectory, traj_id)
    assert traj.status_tag == "bad"

    # Seg 2 marks "good".
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="b" * 32,
                    span_id="2" * 16,
                    started_at=t0 + timedelta(hours=1),
                    status_tag="good",
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()
    await session.refresh(traj)
    assert traj.status_tag == "good"


@pytest.mark.asyncio
async def test_out_of_order_segment_arrival_converges(session):
    """Later segment arrives before earlier one — window converges to correct span."""
    org, agent = await _seed(session)
    traj_id = str(uuid.uuid4())
    t0 = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)

    # Segment 2 arrives first.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="b" * 32,
                    span_id="2" * 16,
                    started_at=t0 + timedelta(hours=1),
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # Segment 1 arrives late.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="a" * 32,
                    span_id="1" * 16,
                    started_at=t0,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    traj = await session.get(Trajectory, traj_id)
    def to_utc(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    # started_at pulled back to segment 1.
    assert to_utc(traj.started_at) == t0
    # ended_at stays at segment 2's end.
    assert to_utc(traj.ended_at) == t0 + timedelta(hours=1, seconds=1)
