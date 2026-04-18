from datetime import datetime, timedelta, timezone

from app.models import Organization, SharedLink, Trajectory, User


async def test_shared_link_creation(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b.co", password_hash="x", display_name="A")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([u, t]); await session.flush()

    link = SharedLink(
        org_id=org.id,
        trajectory_id=t.id,
        created_by=u.id,
        token="share-tok",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    assert link.revoked is False
