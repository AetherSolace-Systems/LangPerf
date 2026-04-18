from app.models import HeuristicHit, Organization, Trajectory


async def test_heuristic_hit_can_be_created(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.flush()
    hit = HeuristicHit(
        org_id=org.id,
        trajectory_id=t.id,
        heuristic="tool_error",
        severity=0.8,
        signature="tool_error:search_orders",
        details={"tool": "search_orders", "message": "timeout"},
    )
    session.add(hit)
    await session.commit()
    assert hit.id is not None
