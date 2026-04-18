from datetime import datetime, timezone

from sqlalchemy import select

from app.heuristics.engine import evaluate_trajectory
from app.models import HeuristicHit, Organization, Span, Trajectory


async def test_engine_persists_hits_for_tool_error(session):
    now = datetime.now(timezone.utc)
    org = Organization(name="default", slug="default"); session.add(org); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    session.add(Span(
        span_id="s1", trace_id="t", trajectory_id=t.id, name="search_orders",
        kind="tool", status_code="ERROR", started_at=now,
        attributes={"tool.name": "search_orders"},
        events=[{"name": "exception", "attributes": {"exception.message": "timeout"}}],
    ))
    await session.commit()

    n_hits = await evaluate_trajectory(session, t.id)
    assert n_hits >= 1
    hits = (await session.execute(select(HeuristicHit).where(HeuristicHit.trajectory_id == t.id))).scalars().all()
    assert any(h.heuristic == "tool_error" for h in hits)


async def test_engine_is_idempotent(session):
    """Running the engine twice should not duplicate hits."""
    now = datetime.now(timezone.utc)
    org = Organization(name="default", slug="default"); session.add(org); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    session.add(Span(
        span_id="s1", trace_id="t", trajectory_id=t.id, name="x",
        kind="tool", status_code="ERROR", started_at=now,
        attributes={"tool.name": "x"},
        events=[],
    ))
    await session.commit()

    await evaluate_trajectory(session, t.id)
    n_after_first = (await session.execute(select(HeuristicHit).where(HeuristicHit.trajectory_id == t.id))).scalars().all()

    await evaluate_trajectory(session, t.id)
    n_after_second = (await session.execute(select(HeuristicHit).where(HeuristicHit.trajectory_id == t.id))).scalars().all()

    assert len(n_after_first) == len(n_after_second)
