from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.deps import get_current_user, require_user
from app.auth.session import create_session
from app.db import get_session
from app.models import Organization, User


def _app_with_deps(session_factory):
    app = FastAPI()

    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    @app.get("/optional")
    async def optional(user=require_user()):
        return {"id": str(user.id), "email": user.email}

    @app.get("/maybe")
    async def maybe(user=get_current_user()):
        return {"email": user.email if user else None}

    return app


async def test_require_user_401_without_cookie(session_factory):
    # Seed a real user so we're in multi-user mode (otherwise single-user mode
    # returns the synthetic user even without a cookie).
    async with session_factory() as s:
        org = Organization(name="default", slug="default")
        s.add(org); await s.flush()
        s.add(User(org_id=org.id, email="seed@seed", password_hash="x", display_name="Seed"))
        await s.commit()

    app = _app_with_deps(session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/optional")
        assert r.status_code == 401


async def test_require_user_succeeds_with_cookie(session_factory):
    async with session_factory() as s:
        org = Organization(name="default", slug="default")
        s.add(org)
        await s.flush()
        user = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
        s.add(user)
        await s.flush()
        sess = await create_session(s, user.id)
        token = sess.token

    app = _app_with_deps(session_factory)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t", cookies={"langperf_session": token}
    ) as c:
        r = await c.get("/optional")
        assert r.status_code == 200
        assert r.json()["email"] == "a@b"


async def test_maybe_returns_synthetic_user_in_single_user_mode(session_factory):
    app = _app_with_deps(session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/maybe")
        assert r.status_code == 200
        assert r.json()["email"] == "single-user@localhost"
