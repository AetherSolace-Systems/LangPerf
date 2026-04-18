from app.auth.mode import DEFAULT_SINGLE_USER, is_single_user_mode
from app.models import Organization, User


async def test_single_user_when_no_users_exist(session):
    assert await is_single_user_mode(session) is True


async def test_multi_user_once_first_user_created(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    user = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    session.add(user)
    await session.commit()
    assert await is_single_user_mode(session) is False


async def test_env_override_forces_single_user(session, monkeypatch):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    user = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    session.add(user)
    await session.commit()
    monkeypatch.setenv("LANGPERF_SINGLE_USER", "1")
    assert await is_single_user_mode(session) is True


def test_synthetic_user_has_stable_id():
    assert DEFAULT_SINGLE_USER.email == "single-user@localhost"
    assert DEFAULT_SINGLE_USER.display_name == "Single User"
