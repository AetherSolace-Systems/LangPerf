import os
import uuid as _uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# The app's own engine is loaded at import time (see app.db). Default to an
# in-memory sqlite so `from app.main import app` works without any external DB.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

# Tests use a separate TEST_DATABASE_URL so CI can run the same suite against
# Postgres (which has percentile_cont / date_trunc and real FK enforcement)
# without touching the app's default engine config.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
USING_POSTGRES = TEST_DATABASE_URL.startswith("postgres")

from app import db as db_module  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, future=True)
    async with eng.begin() as conn:
        if USING_POSTGRES:
            # Postgres test lane reuses one DB across runs; wipe tables first.
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as s:
        yield s


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[db_module.get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_agent(session):
    """Seed an org + default project + agent with a minted raw token.
    The raw token is attached to the agent as `agent.raw_token` (test-only
    attribute) so tests can use it as Bearer auth."""
    from sqlalchemy import select
    from app.auth.agent_token import generate_token, hash_token
    from app.models import Agent, Organization, Project

    async def _factory():
        org = (await session.execute(select(Organization).limit(1))).scalar_one_or_none()
        if org is None:
            org = Organization(id=str(_uuid.uuid4()), name="Acme", slug="acme")
            session.add(org)
            await session.flush()

        proj = (await session.execute(
            select(Project).where(Project.org_id == org.id, Project.slug == "default")
        )).scalar_one_or_none()
        if proj is None:
            proj = Project(id=str(_uuid.uuid4()), org_id=org.id, name="Default", slug="default")
            session.add(proj)
            await session.flush()

        token, prefix = generate_token()
        agent = Agent(
            id=str(_uuid.uuid4()),
            org_id=org.id,
            project_id=proj.id,
            signature=f"sig-{_uuid.uuid4()}",
            name=f"test-agent-{_uuid.uuid4().hex[:8]}",
            language="python",
            token_hash=hash_token(token),
            token_prefix=prefix,
        )
        session.add(agent)
        await session.commit()
        agent.raw_token = token  # type: ignore[attr-defined]  # test-only convenience
        return agent
    return _factory


@pytest_asyncio.fixture
async def seed_agent_with_trajectory(session, seed_agent):
    """Seed an agent PLUS a trajectory row bound to it."""
    from app.models import Trajectory

    async def _factory(*, notes=None):
        agent = await seed_agent()
        traj = Trajectory(
            id=str(_uuid.uuid4()),
            org_id=agent.org_id,
            service_name=agent.name,
            agent_id=agent.id,
            notes=notes,
        )
        session.add(traj)
        await session.commit()
        return agent, traj
    return _factory
