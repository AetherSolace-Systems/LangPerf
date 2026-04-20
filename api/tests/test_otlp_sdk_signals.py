"""SDK-side signals (`mark()` / set-notes) flow into the Trajectory row on ingest.

The SDK stamps `langperf.status_tag` and `langperf.notes` on the root
trajectory span. The OTLP ingest layer reads them off that span and
copies them into ``Trajectory.status_tag`` / ``Trajectory.notes`` so UI
filters reflect the SDK-side signal without the user having to open the
UI to mark the run.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models import Agent, Organization, Project, Trajectory
from app.otlp.decoder import DecodedBundle, DecodedSpan
from app.otlp.ingest import ingest_bundles


# 2026-04-20 00:00 UTC in nanoseconds. Just has to be a plausible recent
# timestamp so the ingest layer's datetime comparison with the existing
# server_default=now() row doesn't hit a naive-vs-aware mismatch under
# sqlite (which strips tzinfo on INSERT).
_START_NS = int(datetime(2026, 4, 20, tzinfo=timezone.utc).timestamp() * 1_000_000_000)
_END_NS = _START_NS + 1_000_000_000  # +1s


def _make_span(
    *,
    trajectory_id: str,
    trace_id: str,
    span_id: str,
    kind: str,
    attributes: dict | None = None,
) -> DecodedSpan:
    """Minimal DecodedSpan for ingest tests. 1-second span."""
    attrs: dict = {"langperf.node.kind": kind}
    if kind == "trajectory":
        attrs["langperf.trajectory.id"] = trajectory_id
    attrs.update(attributes or {})
    return DecodedSpan(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=None,
        name=f"span-{span_id}",
        kind="INTERNAL",
        start_time_unix_nano=_START_NS,
        end_time_unix_nano=_END_NS,
        attributes=attrs,
        events=[],
        status={"code": "UNSET", "message": ""},
        scope={"name": None, "version": None},
    )


async def _seed_org_and_agent(session) -> tuple[Organization, Agent]:
    org = Organization(id=str(uuid.uuid4()), name="Acme", slug="acme")
    project = Project(
        id=str(uuid.uuid4()),
        org_id=org.id,
        name="Default",
        slug="default",
    )
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
async def test_mark_status_tag_propagates_to_trajectory(session):
    org, agent = await _seed_org_and_agent(session)
    traj_id = str(uuid.uuid4())
    bundle: DecodedBundle = {
        "resource": {"attrs": {"service.name": "widget"}},
        "spans": [
            _make_span(
                trajectory_id=traj_id,
                trace_id="a" * 32,
                span_id="b" * 16,
                kind="trajectory",
                attributes={"langperf.status_tag": "bad"},
            )
        ],
    }

    await ingest_bundles(session, [bundle], org_id=org.id, agent=agent)
    await session.commit()

    traj = await session.get(Trajectory, traj_id)
    assert traj is not None
    assert traj.status_tag == "bad"


@pytest.mark.asyncio
async def test_mark_notes_propagate_to_trajectory(session):
    org, agent = await _seed_org_and_agent(session)
    traj_id = str(uuid.uuid4())
    bundle: DecodedBundle = {
        "resource": {"attrs": {"service.name": "widget"}},
        "spans": [
            _make_span(
                trajectory_id=traj_id,
                trace_id="a" * 32,
                span_id="b" * 16,
                kind="trajectory",
                attributes={"langperf.notes": "response was a refusal"},
            )
        ],
    }

    await ingest_bundles(session, [bundle], org_id=org.id, agent=agent)
    await session.commit()

    traj = await session.get(Trajectory, traj_id)
    assert traj.notes == "response was a refusal"


@pytest.mark.asyncio
async def test_mark_signals_only_read_from_trajectory_kind_span(session):
    """Attrs on a non-root span must not leak into the Trajectory row.
    The SDK only stamps these on the trajectory root; treating other
    spans as signal would let noisy instrumentation pollute the filter
    column."""
    org, agent = await _seed_org_and_agent(session)
    traj_id = str(uuid.uuid4())
    bundle: DecodedBundle = {
        "resource": {"attrs": {"service.name": "widget"}},
        "spans": [
            _make_span(
                trajectory_id=traj_id,
                trace_id="a" * 32,
                span_id="b" * 16,
                kind="trajectory",
            ),
            _make_span(
                trajectory_id=traj_id,
                trace_id="a" * 32,
                span_id="c" * 16,
                kind="tool",
                attributes={"langperf.status_tag": "bad"},  # should be ignored
            ),
        ],
    }

    await ingest_bundles(session, [bundle], org_id=org.id, agent=agent)
    await session.commit()

    traj = await session.get(Trajectory, traj_id)
    assert traj.status_tag is None


@pytest.mark.asyncio
async def test_trajectory_service_name_comes_from_authoritative_agent(session):
    """The bearer token identifies the agent — the SDK's advisory
    `service.name` must not overwrite `Trajectory.service_name`.
    Regression test for the "agent name and api key have to match?" UX
    feedback: they shouldn't, and they don't."""
    org, agent = await _seed_org_and_agent(session)
    traj_id = str(uuid.uuid4())
    bundle: DecodedBundle = {
        # SDK sent a `service.name` that doesn't match the registered Agent.
        "resource": {"attrs": {"service.name": "something-the-user-mistyped"}},
        "spans": [
            _make_span(
                trajectory_id=traj_id,
                trace_id="a" * 32,
                span_id="b" * 16,
                kind="trajectory",
            )
        ],
    }

    await ingest_bundles(session, [bundle], org_id=org.id, agent=agent)
    await session.commit()

    traj = await session.get(Trajectory, traj_id)
    assert traj.service_name == agent.name


@pytest.mark.asyncio
async def test_mark_unknown_tag_rejected(session):
    """Unknown tag values stay out of the filter column — UI expects a
    closed set (`good`/`bad`/`interesting`/`todo`)."""
    org, agent = await _seed_org_and_agent(session)
    traj_id = str(uuid.uuid4())
    bundle: DecodedBundle = {
        "resource": {"attrs": {"service.name": "widget"}},
        "spans": [
            _make_span(
                trajectory_id=traj_id,
                trace_id="a" * 32,
                span_id="b" * 16,
                kind="trajectory",
                attributes={"langperf.status_tag": "weird-custom"},
            )
        ],
    }

    await ingest_bundles(session, [bundle], org_id=org.id, agent=agent)
    await session.commit()

    traj = await session.get(Trajectory, traj_id)
    assert traj.status_tag is None
