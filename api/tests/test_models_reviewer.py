from app.models import Organization, Trajectory, User


async def test_trajectory_can_be_assigned(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b.co", password_hash="x", display_name="A")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([u, t]); await session.flush()
    t.assigned_user_id = u.id
    await session.commit()
    await session.refresh(t)
    assert t.assigned_user_id == u.id
