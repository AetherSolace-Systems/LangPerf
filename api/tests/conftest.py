import os
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
