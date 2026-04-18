from datetime import datetime, timezone

from app.auth.session import create_session, delete_session, get_session_by_token
from app.models import Organization, User


async def _user(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    user = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    session.add(user)
    await session.commit()
    return user


async def test_create_and_lookup_session(session):
    user = await _user(session)
    sess = await create_session(session, user.id)
    assert sess.token
    assert len(sess.token) >= 32
    found = await get_session_by_token(session, sess.token)
    assert found is not None
    assert found.user_id == user.id


async def test_expired_session_is_not_returned(session):
    user = await _user(session)
    sess = await create_session(session, user.id)
    sess.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    await session.commit()
    found = await get_session_by_token(session, sess.token)
    assert found is None


async def test_delete_session(session):
    user = await _user(session)
    sess = await create_session(session, user.id)
    await delete_session(session, sess.token)
    found = await get_session_by_token(session, sess.token)
    assert found is None
