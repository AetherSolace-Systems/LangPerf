from app.models import FailureMode, Organization, Trajectory, TrajectoryFailureMode, User


async def test_failure_mode_attached_to_trajectory(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b.co", password_hash="x", display_name="A")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([u, t]); await session.flush()
    fm = FailureMode(org_id=org.id, slug="wrong_tool", label="Wrong tool", color="warn")
    session.add(fm); await session.flush()
    link = TrajectoryFailureMode(trajectory_id=t.id, failure_mode_id=fm.id, tagged_by=u.id)
    session.add(link)
    await session.commit()
    assert link.trajectory_id == t.id
