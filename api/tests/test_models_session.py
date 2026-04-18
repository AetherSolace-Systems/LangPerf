from datetime import datetime, timedelta, timezone

from app.models import Organization, Session as SessionModel, User


async def test_session_can_be_created(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    user = User(org_id=org.id, email="a@b.com", password_hash="x", display_name="A")
    session.add(user)
    await session.flush()

    sess = SessionModel(
        token="abc123",
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    session.add(sess)
    await session.commit()
    await session.refresh(sess)

    assert sess.token == "abc123"
    assert sess.user_id == user.id
