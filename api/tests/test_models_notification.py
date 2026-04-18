from app.models import Notification, Organization, User


async def test_notification_for_user(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    u = User(org_id=org.id, email="a@b.co", password_hash="x", display_name="A")
    session.add(u)
    await session.flush()

    n = Notification(
        org_id=org.id,
        user_id=u.id,
        kind="mention",
        payload={"comment_id": "x"},
    )
    session.add(n)
    await session.commit()
    await session.refresh(n)
    assert n.read_at is None
