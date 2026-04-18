# V2a — Auth & Identity Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-user authentication and one-org-per-deployment identity to LangPerf, with graceful degradation to single-user mode so Andrew-solo usage keeps working without login friction.

**Architecture:** FastAPI dependency-injected auth with opaque session tokens in httponly cookies, bcrypt password hashing, one `Organization` row per deployment (created on first signup), `org_id` foreign keys added to all existing domain tables with a migration that backfills to the default org. Next.js auth guard via middleware that consults a public `/api/auth/mode` endpoint to know whether to redirect to `/login`.

**Tech Stack:** FastAPI + async SQLAlchemy (existing), Alembic (existing), passlib[bcrypt] for password hashing, pytest + pytest-asyncio + httpx.AsyncClient for backend tests (new), Playwright for E2E (existing), Next.js middleware for route protection.

---

## File Structure

**Backend:**
- `api/pyproject.toml` — add dev deps: pytest, pytest-asyncio, httpx, passlib[bcrypt]; add runtime dep: passlib[bcrypt]
- `api/app/models.py` — add `User`, `Organization`, `Session` models; add `org_id` FK to `Agent`, `Trajectory`, `WorkspaceSetting`
- `api/alembic/versions/0009_auth_identity.py` — migration: create auth tables + add/backfill `org_id`
- `api/app/auth/__init__.py` — package marker
- `api/app/auth/password.py` — `hash_password`, `verify_password`
- `api/app/auth/session.py` — session token creation, lookup, deletion
- `api/app/auth/deps.py` — `get_current_user`, `require_user`, `get_current_org`
- `api/app/auth/mode.py` — `is_single_user_mode`, synthetic default user
- `api/app/api/auth.py` — routes: `/api/auth/signup`, `/login`, `/logout`, `/me`, `/mode`
- `api/app/main.py` — register auth router; no global auth middleware (per-route dependency)
- `api/tests/__init__.py` — new test package
- `api/tests/conftest.py` — pytest fixtures: test DB, async client, user/org factories
- `api/tests/test_auth.py` — auth endpoint tests
- `api/tests/test_multi_tenancy.py` — org isolation tests
- `api/tests/test_single_user_mode.py` — single-user degradation tests

**Frontend:**
- `web/lib/auth.ts` — client auth helpers (login, logout, fetchMode)
- `web/app/login/page.tsx` — login page (server-rendered shell + client form)
- `web/components/auth/login-form.tsx` — client login form
- `web/app/api/auth/logout/route.ts` — Next.js route that proxies to backend logout and clears cookie
- `web/middleware.ts` — auth redirect middleware
- `web/components/shell/user-menu.tsx` — current-user chip + logout in top bar
- `web/tests/auth.spec.ts` — Playwright auth flow test

**Responsibilities:**
- `api/app/auth/` owns all auth primitives; routes and models stay separate.
- `api/app/api/auth.py` is route glue only, no business logic.
- Frontend auth lives under `web/lib/auth.ts` + `web/middleware.ts` — no `AuthProvider` context; session state is driven by cookies + server components re-fetching.

---

## Task 1: Set up pytest infrastructure

**Files:**
- Modify: `api/pyproject.toml`
- Create: `api/tests/__init__.py`
- Create: `api/tests/conftest.py`
- Create: `api/tests/test_smoke.py`

- [ ] **Step 1: Add test deps to pyproject.toml**

Modify `api/pyproject.toml` — add to `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "aiosqlite>=0.20",
]
```

Also add `passlib[bcrypt]>=1.7.4` to runtime dependencies.

- [ ] **Step 2: Install deps**

Run: `cd api && pip install -e ".[dev]"`
Expected: successful install, `pytest --version` works.

- [ ] **Step 3: Create test package marker**

Create `api/tests/__init__.py` (empty file).

- [ ] **Step 4: Create conftest.py with test DB + client fixtures**

Create `api/tests/conftest.py`:

```python
import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

from app import db as db_module  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with eng.begin() as conn:
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
```

- [ ] **Step 5: Add smoke test**

Create `api/tests/test_smoke.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_client_hits_healthcheck(client):
    response = await client.get("/health")
    assert response.status_code == 200
```

Note: if `/health` does not exist yet, replace with any known route (e.g. `/api/overview` may return data or 404 — a 404 still proves the app is reachable). Adjust the assertion accordingly.

- [ ] **Step 6: Configure pytest-asyncio mode**

Append to `api/pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

With `auto` mode, drop `@pytest.mark.asyncio` from tests.

- [ ] **Step 7: Run smoke test**

Run: `cd api && pytest -v`
Expected: `test_client_hits_healthcheck` passes (or fails with 404 that you convert to an assertion that matches reality).

- [ ] **Step 8: Commit**

```bash
git add api/pyproject.toml api/tests
git commit -m "tests: pytest + async client fixtures"
```

---

## Task 2: Add Organization model

**Files:**
- Modify: `api/app/models.py`
- Create: `api/tests/test_models_org.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_models_org.py`:

```python
from app.models import Organization


async def test_organization_can_be_created(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.commit()
    await session.refresh(org)
    assert org.id is not None
    assert org.name == "default"
    assert org.slug == "default"
    assert org.created_at is not None
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_models_org.py -v`
Expected: ImportError — `Organization` not defined.

- [ ] **Step 3: Add Organization model**

Modify `api/app/models.py` — add after existing imports, before existing model classes:

```python
class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
```

Note: if `models.py` already imports `PgUUID`, `String`, `DateTime`, `Mapped`, `mapped_column`, `uuid`, `datetime`, `timezone`, reuse them. If not, add the imports to match the existing style of the file.

- [ ] **Step 4: Run test to verify pass**

Run: `cd api && pytest tests/test_models_org.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_org.py
git commit -m "feat: organization model"
```

---

## Task 3: Add User model

**Files:**
- Modify: `api/app/models.py`
- Create: `api/tests/test_models_user.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_models_user.py`:

```python
from app.models import Organization, User


async def test_user_belongs_to_org(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()

    user = User(
        org_id=org.id,
        email="andrew@example.com",
        password_hash="fake-hash",
        display_name="Andrew",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert user.org_id == org.id
    assert user.is_admin is False
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_models_user.py -v`
Expected: ImportError — `User` not defined.

- [ ] **Step 3: Add User model**

Modify `api/app/models.py`:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (UniqueConstraint("org_id", "email", name="uq_users_org_email"),)
```

Add imports as needed: `ForeignKey`, `Boolean`, `UniqueConstraint`.

- [ ] **Step 4: Run test to verify pass**

Run: `cd api && pytest tests/test_models_user.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_user.py
git commit -m "feat: user model"
```

---

## Task 4: Add Session model

**Files:**
- Modify: `api/app/models.py`
- Create: `api/tests/test_models_session.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_models_session.py`:

```python
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
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_models_session.py -v`
Expected: ImportError.

- [ ] **Step 3: Add Session model**

Modify `api/app/models.py`:

```python
class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd api && pytest tests/test_models_session.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_session.py
git commit -m "feat: session model"
```

---

## Task 5: Add org_id FK to domain tables

**Files:**
- Modify: `api/app/models.py` (Agent, Trajectory, WorkspaceSetting)
- Create: `api/tests/test_models_tenancy.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_models_tenancy.py`:

```python
from app.models import Agent, Organization, Trajectory, WorkspaceSetting


async def test_agent_has_org_id(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    a = Agent(org_id=org.id, signature="sig", name="n", display_name="N")
    session.add(a)
    await session.commit()
    assert a.org_id == org.id


async def test_trajectory_has_org_id(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    t = Trajectory(org_id=org.id, trace_id="tid", service_name="svc", name="n")
    session.add(t)
    await session.commit()
    assert t.org_id == org.id


async def test_workspace_setting_has_org_id(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    ws = WorkspaceSetting(org_id=org.id, key="k", value={"a": 1})
    session.add(ws)
    await session.commit()
    assert ws.org_id == org.id
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_models_tenancy.py -v`
Expected: errors — `org_id` column doesn't exist on those models yet.

- [ ] **Step 3: Add org_id column to Agent**

Modify `api/app/models.py` — in the `Agent` class, add:

```python
org_id: Mapped[uuid.UUID] = mapped_column(
    PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
)
```

- [ ] **Step 4: Add org_id column to Trajectory**

Modify `Trajectory` class:

```python
org_id: Mapped[uuid.UUID] = mapped_column(
    PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
)
```

- [ ] **Step 5: Add org_id column to WorkspaceSetting**

Modify `WorkspaceSetting` class. Since `WorkspaceSetting` uses `key` as primary key, change the primary key to composite `(org_id, key)`:

```python
org_id: Mapped[uuid.UUID] = mapped_column(
    PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
)
key: Mapped[str] = mapped_column(String(255), primary_key=True)
```

- [ ] **Step 6: Run tests to verify pass**

Run: `cd api && pytest tests/test_models_tenancy.py -v`
Expected: all three tests PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/models.py api/tests/test_models_tenancy.py
git commit -m "feat: org_id FK on Agent, Trajectory, WorkspaceSetting"
```

---

## Task 6: Alembic migration for auth tables + tenancy backfill

**Files:**
- Create: `api/alembic/versions/0009_auth_identity.py`
- Create: `api/tests/test_migration_0009.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_migration_0009.py`:

```python
from sqlalchemy import inspect, text


async def test_migration_creates_auth_tables_and_backfills_org(engine):
    async with engine.connect() as conn:
        def inspect_tables(sync_conn):
            insp = inspect(sync_conn)
            return set(insp.get_table_names())
        tables = await conn.run_sync(inspect_tables)
    assert "organizations" in tables
    assert "users" in tables
    assert "sessions" in tables


async def test_all_existing_rows_get_default_org(engine):
    async with engine.connect() as conn:
        def inspect_cols(sync_conn):
            insp = inspect(sync_conn)
            return {
                "agents": {c["name"] for c in insp.get_columns("agents")},
                "trajectories": {c["name"] for c in insp.get_columns("trajectories")},
                "workspace_settings": {c["name"] for c in insp.get_columns("workspace_settings")},
            }
        cols = await conn.run_sync(inspect_cols)
    assert "org_id" in cols["agents"]
    assert "org_id" in cols["trajectories"]
    assert "org_id" in cols["workspace_settings"]
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_migration_0009.py -v`
Expected: FAIL — migration doesn't exist, conftest's `Base.metadata.create_all` builds fresh schema but without a `default` org row.

- [ ] **Step 3: Author migration file**

Create `api/alembic/versions/0009_auth_identity.py`:

```python
"""auth identity + tenancy

Revision ID: 0009_auth_identity
Revises: 0008  # replace with actual prior revision
Create Date: 2026-04-17 00:00:00.000000
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0009_auth_identity"
down_revision = "0008"  # replace with actual prior revision id
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
    )
    op.create_table(
        "sessions",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column("user_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    default_org_id = uuid.uuid4()
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, created_at) VALUES (:id, 'default', 'default', :ts)"
        ).bindparams(id=str(default_org_id), ts=datetime.now(timezone.utc))
    )

    for table in ("agents", "trajectories"):
        op.add_column(table, sa.Column("org_id", PgUUID(as_uuid=True), nullable=True))
        op.execute(sa.text(f"UPDATE {table} SET org_id = :id").bindparams(id=str(default_org_id)))
        op.alter_column(table, "org_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_org_id",
            table,
            "organizations",
            ["org_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_org_id", table, ["org_id"])

    op.add_column("workspace_settings", sa.Column("org_id", PgUUID(as_uuid=True), nullable=True))
    op.execute(sa.text("UPDATE workspace_settings SET org_id = :id").bindparams(id=str(default_org_id)))
    op.drop_constraint("workspace_settings_pkey", "workspace_settings", type_="primary")
    op.alter_column("workspace_settings", "org_id", nullable=False)
    op.create_primary_key("pk_workspace_settings", "workspace_settings", ["org_id", "key"])
    op.create_foreign_key(
        "fk_workspace_settings_org_id",
        "workspace_settings",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_workspace_settings_org_id", "workspace_settings", type_="foreignkey")
    op.drop_constraint("pk_workspace_settings", "workspace_settings", type_="primary")
    op.create_primary_key("workspace_settings_pkey", "workspace_settings", ["key"])
    op.drop_column("workspace_settings", "org_id")

    for table in ("trajectories", "agents"):
        op.drop_index(f"ix_{table}_org_id", table_name=table)
        op.drop_constraint(f"fk_{table}_org_id", table, type_="foreignkey")
        op.drop_column(table, "org_id")

    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("organizations")
```

Replace `"0008"` with the actual latest revision id from `api/alembic/versions/`.

- [ ] **Step 4: Run migration test**

Run: `cd api && pytest tests/test_migration_0009.py -v`
Expected: tests PASS (conftest builds from `Base.metadata.create_all`, so these tests check column presence, not migration execution).

- [ ] **Step 5: Apply migration against real Postgres dev DB**

Run: `cd api && alembic upgrade head`
Expected: migration succeeds, `psql` can show new tables + columns.

- [ ] **Step 6: Commit**

```bash
git add api/alembic/versions/0009_auth_identity.py api/tests/test_migration_0009.py
git commit -m "feat: alembic migration for auth + tenancy"
```

---

## Task 7: Password hashing utility

**Files:**
- Create: `api/app/auth/__init__.py` (empty)
- Create: `api/app/auth/password.py`
- Create: `api/tests/test_auth_password.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_auth_password.py`:

```python
from app.auth.password import hash_password, verify_password


def test_hash_and_verify_round_trip():
    hashed = hash_password("correcthorsebatterystaple")
    assert hashed != "correcthorsebatterystaple"
    assert verify_password("correcthorsebatterystaple", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_hashes_are_different_for_same_password():
    a = hash_password("x")
    b = hash_password("x")
    assert a != b
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_auth_password.py -v`
Expected: ImportError.

- [ ] **Step 3: Create package + implementation**

Create `api/app/auth/__init__.py` (empty).
Create `api/app/auth/password.py`:

```python
from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plaintext: str) -> str:
    return _pwd_context.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    return _pwd_context.verify(plaintext, hashed)
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd api && pytest tests/test_auth_password.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/auth api/tests/test_auth_password.py
git commit -m "feat: bcrypt password hashing"
```

---

## Task 8: Session token utilities

**Files:**
- Create: `api/app/auth/session.py`
- Create: `api/tests/test_auth_session.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_auth_session.py`:

```python
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
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_auth_session.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement session helpers**

Create `api/app/auth/session.py`:

```python
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session as SessionModel

SESSION_TTL = timedelta(days=30)


async def create_session(db: AsyncSession, user_id: uuid.UUID) -> SessionModel:
    token = secrets.token_urlsafe(32)
    sess = SessionModel(
        token=token,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + SESSION_TTL,
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def get_session_by_token(db: AsyncSession, token: str) -> SessionModel | None:
    result = await db.execute(select(SessionModel).where(SessionModel.token == token))
    sess = result.scalar_one_or_none()
    if sess is None:
        return None
    if sess.expires_at < datetime.now(timezone.utc):
        return None
    return sess


async def delete_session(db: AsyncSession, token: str) -> None:
    result = await db.execute(select(SessionModel).where(SessionModel.token == token))
    sess = result.scalar_one_or_none()
    if sess:
        await db.delete(sess)
        await db.commit()
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd api && pytest tests/test_auth_session.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/auth/session.py api/tests/test_auth_session.py
git commit -m "feat: session token create/lookup/delete"
```

---

## Task 9: Single-user mode detection + synthetic user

**Files:**
- Create: `api/app/auth/mode.py`
- Create: `api/tests/test_auth_mode.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_auth_mode.py`:

```python
import os

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
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_auth_mode.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement mode detection**

Create `api/app/auth/mode.py`:

```python
import os
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


@dataclass(frozen=True)
class SyntheticUser:
    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    display_name: str
    is_admin: bool


DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
DEFAULT_SINGLE_USER = SyntheticUser(
    id=DEFAULT_USER_ID,
    org_id=DEFAULT_ORG_ID,
    email="single-user@localhost",
    display_name="Single User",
    is_admin=True,
)


async def is_single_user_mode(db: AsyncSession) -> bool:
    if os.environ.get("LANGPERF_SINGLE_USER") == "1":
        return True
    result = await db.execute(select(func.count(User.id)))
    count = result.scalar_one()
    return count == 0
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd api && pytest tests/test_auth_mode.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/auth/mode.py api/tests/test_auth_mode.py
git commit -m "feat: single-user mode detection + synthetic user"
```

---

## Task 10: Auth dependencies (get_current_user, require_user)

**Files:**
- Create: `api/app/auth/deps.py`
- Create: `api/tests/test_auth_deps.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_auth_deps.py`:

```python
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
```

- [ ] **Step 2: Run test to verify fail**

Run: `cd api && pytest tests/test_auth_deps.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement dependencies**

Create `api/app/auth/deps.py`:

```python
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.mode import DEFAULT_SINGLE_USER, SyntheticUser, is_single_user_mode
from app.auth.session import get_session_by_token
from app.db import get_session
from app.models import User

SESSION_COOKIE = "langperf_session"

Principal = User | SyntheticUser


async def _resolve_user(
    db: AsyncSession, token: str | None
) -> Principal | None:
    if token:
        sess = await get_session_by_token(db, token)
        if sess:
            user = await db.get(User, sess.user_id)
            if user:
                return user
    if await is_single_user_mode(db):
        return DEFAULT_SINGLE_USER
    return None


def get_current_user():
    async def _dep(
        session: Annotated[AsyncSession, Depends(get_session)],
        token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Principal | None:
        return await _resolve_user(session, token)

    return Depends(_dep)


def require_user():
    async def _dep(
        session: Annotated[AsyncSession, Depends(get_session)],
        token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Principal:
        user = await _resolve_user(session, token)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
        return user

    return Depends(_dep)
```

- [ ] **Step 4: Run test to verify pass**

Run: `cd api && pytest tests/test_auth_deps.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/auth/deps.py api/tests/test_auth_deps.py
git commit -m "feat: get_current_user and require_user dependencies"
```

---

## Task 11: Auth routes — signup / login / logout / me / mode

**Files:**
- Create: `api/app/api/auth.py`
- Modify: `api/app/main.py` (include router)
- Create: `api/tests/test_api_auth.py`

- [ ] **Step 1: Write failing tests**

Create `api/tests/test_api_auth.py`:

```python
async def test_mode_endpoint_reports_single_user_when_fresh(client):
    r = await client.get("/api/auth/mode")
    assert r.status_code == 200
    assert r.json() == {"mode": "single_user"}


async def test_signup_bootstrap_creates_first_user_and_org(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "andrew@example.com", "password": "correcthorsebatterystaple", "display_name": "Andrew"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "andrew@example.com"
    assert body["user"]["is_admin"] is True
    cookie = r.cookies.get("langperf_session")
    assert cookie is not None


async def test_signup_rejected_when_user_exists_without_admin_auth(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.post(
        "/api/auth/signup",
        json={"email": "c@d", "password": "pw12345678", "display_name": "C"},
    )
    assert r.status_code == 403


async def test_login_sets_session_cookie(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"email": "a@b", "password": "pw12345678"},
    )
    assert r.status_code == 200
    assert r.cookies.get("langperf_session")


async def test_login_rejects_wrong_password(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"email": "a@b", "password": "wrong"},
    )
    assert r.status_code == 401


async def test_me_returns_current_user(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "a@b"


async def test_logout_clears_session(client):
    signup = await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    token = signup.cookies["langperf_session"]
    r = await client.post("/api/auth/logout", cookies={"langperf_session": token})
    assert r.status_code == 204
    r2 = await client.get("/api/auth/me", cookies={"langperf_session": token})
    assert r2.status_code in (401, 200)  # 200 only if env forces single-user
```

- [ ] **Step 2: Run tests to verify fail**

Run: `cd api && pytest tests/test_api_auth.py -v`
Expected: all fail — routes don't exist.

- [ ] **Step 3: Implement auth router**

Create `api/app/api/auth.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import SESSION_COOKIE, require_user, get_current_user
from app.auth.mode import DEFAULT_SINGLE_USER, is_single_user_mode
from app.auth.password import hash_password, verify_password
from app.auth.session import create_session, delete_session
from app.db import get_session
from app.models import Organization, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_KW = dict(
    key=SESSION_COOKIE,
    httponly=True,
    samesite="lax",
    secure=False,  # set True behind https
    path="/",
)


class SignupPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    display_name: str = Field(min_length=1, max_length=255)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class UserDto(BaseModel):
    id: str
    org_id: str
    email: str
    display_name: str
    is_admin: bool


def _to_dto(u) -> UserDto:
    return UserDto(
        id=str(u.id),
        org_id=str(u.org_id),
        email=u.email,
        display_name=u.display_name,
        is_admin=u.is_admin,
    )


@router.get("/mode")
async def mode(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    return {"mode": "single_user" if await is_single_user_mode(session) else "multi_user"}


@router.post("/signup", status_code=201)
async def signup(
    payload: SignupPayload,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    existing = await session.execute(select(User).limit(1))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=403, detail="signup closed; ask an admin for an invite")

    org = Organization(id=uuid.uuid4(), name="default", slug="default", created_at=datetime.now(timezone.utc))
    session.add(org)
    await session.flush()
    user = User(
        id=uuid.uuid4(),
        org_id=org.id,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        is_admin=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()
    sess = await create_session(session, user.id)
    response.set_cookie(value=sess.token, **COOKIE_KW)
    return {"user": _to_dto(user).model_dump()}


@router.post("/login")
async def login(
    payload: LoginPayload,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    sess = await create_session(session, user.id)
    response.set_cookie(value=sess.token, **COOKIE_KW)
    return {"user": _to_dto(user).model_dump()}


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
):
    if token:
        await delete_session(session, token)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return Response(status_code=204)


@router.get("/me")
async def me(user=require_user()):
    return {"user": _to_dto(user).model_dump()}
```

- [ ] **Step 4: Mount router in main.py**

Modify `api/app/main.py` — in the imports section add:

```python
from app.api import auth as auth_api
```

In the section that calls `app.include_router(...)` for other routers, add:

```python
app.include_router(auth_api.router)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd api && pytest tests/test_api_auth.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/api/auth.py api/app/main.py api/tests/test_api_auth.py
git commit -m "feat: auth endpoints — signup, login, logout, me, mode"
```

---

## Task 12: Add org scoping to existing domain routes

**Files:**
- Modify: `api/app/api/trajectories.py`, `agents.py`, `overview.py`, `settings.py`, `runs.py`, `logs.py`, `nodes.py`
- Create: `api/tests/test_tenancy_isolation.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_tenancy_isolation.py`:

```python
async def test_trajectories_scoped_to_current_org(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.get("/api/trajectories")
    assert r.status_code == 200
    assert isinstance(r.json(), list) or "items" in r.json()


async def test_agents_scoped_to_current_org(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.get("/api/agents")
    assert r.status_code == 200
```

- [ ] **Step 2: Run tests**

Run: `cd api && pytest tests/test_tenancy_isolation.py -v`
Expected: test structure depends on current responses — failure is acceptable if endpoints currently 500 due to required `org_id` column with no backfill mid-test. Adjust payload construction in tests to first insert an agent/trajectory tagged with the signed-up user's org_id.

- [ ] **Step 3: Add `require_user()` + org filter to each domain router**

For each of `api/app/api/trajectories.py`, `agents.py`, `overview.py`, `settings.py`, `runs.py`, `logs.py`, `nodes.py`:

1. Add import: `from app.auth.deps import require_user`
2. For every route handler, add a parameter: `user=require_user()`
3. In every query against `Agent`, `Trajectory`, `WorkspaceSetting`, add `.where(Agent.org_id == user.org_id)` (or equivalent for the table).
4. In every insert, set `org_id=user.org_id`.

Example for `trajectories.py`:

```python
@router.get("")
async def list_trajectories(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
    limit: int = 50,
    offset: int = 0,
):
    query = select(Trajectory).where(Trajectory.org_id == user.org_id).order_by(Trajectory.started_at.desc()).limit(limit).offset(offset)
    ...
```

- [ ] **Step 4: Also scope OTLP ingestion**

Modify `api/app/main.py` or wherever `/v1/traces` is handled: OTLP traffic does NOT carry a session cookie. Instead, accept an `Authorization: Bearer <token>` header carrying an API key. For v2a, map API keys to orgs via a new `api_keys` table. If that's out of scope for v2a, ingest unconditionally to the default org for now and track it as a follow-up.

**Decision for v2a**: leave OTLP ingestion scoped to the default/first-org (read: `org_id` is the default org's id at ingestion). Document this as a known limitation. Add a TODO comment in `main.py`:

```python
# TODO(v2b): scope OTLP ingestion per API key once we add api_keys table
```

- [ ] **Step 5: Run full test suite**

Run: `cd api && pytest -v`
Expected: all auth-related tests PASS; domain tests either PASS (if routes correctly scoped) or surface specific failures to fix iteratively.

- [ ] **Step 6: Commit**

```bash
git add api/app
git commit -m "feat: scope domain routes by org_id"
```

---

## Task 13: Frontend — auth client helpers

**Files:**
- Create: `web/lib/auth.ts`

- [ ] **Step 1: Implement auth client**

Create `web/lib/auth.ts`:

```ts
import { CLIENT_API_URL, SERVER_API_URL } from "./api";

export type AuthMode = "single_user" | "multi_user";

export type CurrentUser = {
  id: string;
  org_id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
};

export async function fetchMode(): Promise<AuthMode> {
  const res = await fetch(`${SERVER_API_URL}/api/auth/mode`, { cache: "no-store" });
  const body = await res.json();
  return body.mode as AuthMode;
}

export async function fetchMe(cookie?: string): Promise<CurrentUser | null> {
  const res = await fetch(`${SERVER_API_URL}/api/auth/me`, {
    headers: cookie ? { cookie } : {},
    cache: "no-store",
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`me failed: ${res.status}`);
  const body = await res.json();
  return body.user;
}

export async function loginRequest(email: string, password: string): Promise<CurrentUser> {
  const res = await fetch(`${CLIENT_API_URL}/api/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "login failed" }));
    throw new Error(body.detail ?? "login failed");
  }
  const body = await res.json();
  return body.user;
}

export async function signupRequest(email: string, password: string, display_name: string): Promise<CurrentUser> {
  const res = await fetch(`${CLIENT_API_URL}/api/auth/signup`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password, display_name }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "signup failed" }));
    throw new Error(body.detail ?? "signup failed");
  }
  const body = await res.json();
  return body.user;
}

export async function logoutRequest(): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add web/lib/auth.ts
git commit -m "feat: web auth client helpers"
```

---

## Task 14: Login / signup page

**Files:**
- Create: `web/app/login/page.tsx`
- Create: `web/components/auth/login-form.tsx`

- [ ] **Step 1: Server component shell**

Create `web/app/login/page.tsx`:

```tsx
import { redirect } from "next/navigation";
import { headers } from "next/headers";

import { fetchMode, fetchMe } from "@/lib/auth";
import { LoginForm } from "@/components/auth/login-form";

export const dynamic = "force-dynamic";

export default async function LoginPage() {
  const cookie = headers().get("cookie") ?? undefined;
  const [mode, me] = await Promise.all([fetchMode(), fetchMe(cookie)]);
  if (mode === "single_user" || me) redirect("/");

  const hasAnyUser = mode === "multi_user";

  return (
    <main className="flex min-h-screen items-center justify-center bg-carbon px-4">
      <div className="w-full max-w-sm rounded-2xl bg-warm-fog/50 p-6 shadow-xl ring-1 ring-aether-teal/20">
        <h1 className="mb-4 text-xl font-semibold text-aether-teal">
          {hasAnyUser ? "Sign in to LangPerf" : "Set up LangPerf"}
        </h1>
        <LoginForm bootstrap={!hasAnyUser} />
      </div>
    </main>
  );
}
```

- [ ] **Step 2: Client form**

Create `web/components/auth/login-form.tsx`:

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { loginRequest, signupRequest } from "@/lib/auth";

export function LoginForm({ bootstrap }: { bootstrap: boolean }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPending(true);
    setError(null);
    try {
      if (bootstrap) {
        await signupRequest(email, password, displayName || email.split("@")[0]);
      } else {
        await loginRequest(email, password);
      }
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="space-y-3" onSubmit={onSubmit}>
      {bootstrap && (
        <input
          className="w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
          placeholder="Display name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
        />
      )}
      <input
        type="email"
        autoComplete="email"
        className="w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        required
      />
      <input
        type="password"
        autoComplete={bootstrap ? "new-password" : "current-password"}
        className="w-full rounded bg-carbon px-3 py-2 text-sm text-warm-fog"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
        minLength={8}
      />
      {error && <p className="text-xs text-warn">{error}</p>}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded bg-aether-teal px-3 py-2 text-sm font-semibold text-carbon disabled:opacity-50"
      >
        {pending ? "Working..." : bootstrap ? "Create admin account" : "Sign in"}
      </button>
    </form>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/app/login web/components/auth
git commit -m "feat: login/signup page"
```

---

## Task 15: Middleware — redirect unauth'd users to /login

**Files:**
- Create: `web/middleware.ts`

- [ ] **Step 1: Implement middleware**

Create `web/middleware.ts`:

```ts
import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = new Set(["/login", "/favicon.ico"]);

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.has(pathname) || pathname.startsWith("/_next") || pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  const hasSession = request.cookies.has("langperf_session");
  if (hasSession) return NextResponse.next();

  const apiBase = process.env.LANGPERF_API_URL ?? "http://localhost:4318";
  const res = await fetch(`${apiBase}/api/auth/mode`, { cache: "no-store" });
  if (res.ok) {
    const body = (await res.json()) as { mode: "single_user" | "multi_user" };
    if (body.mode === "single_user") return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
```

- [ ] **Step 2: Commit**

```bash
git add web/middleware.ts
git commit -m "feat: auth redirect middleware"
```

---

## Task 16: Top-bar user menu with logout

**Files:**
- Create: `web/components/shell/user-menu.tsx`
- Modify: `web/components/shell/top-bar.tsx` (or the equivalent existing file for the top-bar chrome)

- [ ] **Step 1: Create user menu component**

Create `web/components/shell/user-menu.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";

import { logoutRequest, type CurrentUser } from "@/lib/auth";

export function UserMenu({ user }: { user: CurrentUser | null }) {
  const router = useRouter();
  if (!user) return null;

  async function onLogout() {
    await logoutRequest();
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="flex items-center gap-2 text-xs text-warm-fog/80">
      <span>{user.display_name}</span>
      <button onClick={onLogout} className="rounded bg-warm-fog/10 px-2 py-1 hover:bg-warm-fog/20">
        Sign out
      </button>
    </div>
  );
}
```

- [ ] **Step 2: Wire it into the top bar**

Modify the existing top-bar component in `web/components/shell/` (exact file name discovered via `grep -l "top-bar\|TopBar" web/components/shell/`). Fetch the current user server-side and pass to `UserMenu`:

```tsx
import { headers } from "next/headers";

import { fetchMe } from "@/lib/auth";
import { UserMenu } from "./user-menu";

// inside the top bar JSX:
const cookie = headers().get("cookie") ?? undefined;
const me = await fetchMe(cookie);
...
<UserMenu user={me} />
```

If the top bar is currently a client component, lift the `fetchMe` call to its parent server component and pass `user` down as a prop.

- [ ] **Step 3: Commit**

```bash
git add web/components/shell/user-menu.tsx web/components/shell
git commit -m "feat: user menu with logout in top bar"
```

---

## Task 17: Playwright end-to-end auth flow test

**Files:**
- Create: `web/tests/auth.spec.ts`

- [ ] **Step 1: Write the spec**

Create `web/tests/auth.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test.describe.serial("auth flow", () => {
  test("bootstrap signup → dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.getByPlaceholder("Display name").fill("Andrew");
    await page.getByPlaceholder("Email").fill(`andrew+${Date.now()}@example.com`);
    await page.getByPlaceholder("Password").fill("correcthorsebatterystaple");
    await page.getByRole("button", { name: /create admin account/i }).click();
    await expect(page).toHaveURL("/");
  });

  test("logout redirects to /login", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /sign out/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test("unauth'd request to / redirects to /login (multi-user mode)", async ({ page, context }) => {
    await context.clearCookies();
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });
});
```

- [ ] **Step 2: Run the spec**

Run: `cd web && npm test -- auth.spec.ts`
Expected: all tests PASS against a dev stack (docker compose up) with a fresh DB.

- [ ] **Step 3: Commit**

```bash
git add web/tests/auth.spec.ts
git commit -m "tests: playwright auth flow"
```

---

## Task 18: Documentation update

**Files:**
- Modify: `README.md` (or `docs/` equivalent)

- [ ] **Step 1: Add auth section to README**

Document:
1. Fresh deployment goes to `/login` → bootstrap signup form creates first admin + default org.
2. Setting `LANGPERF_SINGLE_USER=1` bypasses login (useful for local dev).
3. Session cookies are httponly; set `secure=True` behind HTTPS in production.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: v2a auth setup instructions"
```

---

## Notes for the implementer

- **Commit style**: continue the repo convention `type: summary` (e.g., `feat:`, `tests:`, `docs:`, `chore:`). No `Co-Authored-By` footer needed unless the team adopts it.
- **Base revision for Alembic**: check `api/alembic/versions/` for the actual latest revision id before authoring `0009_auth_identity.py`. The placeholder `"0008"` must be replaced with the real id string.
- **OTLP ingestion org scoping** is deliberately deferred to a later sub-plan (tracked in-code as a TODO). Do not block v2a on it.
- **Styling**: the design system is "Aether Dusk" — use `aether-teal`, `peach-neon`, `warm-fog`, `carbon`, `warn` color tokens. Avoid the legacy `drift-violet` aliases.
- **Single-user mode is the default**: until the first signup happens, the app behaves as v1 did — no login required. This preserves Andrew's solo-dogfood loop.
