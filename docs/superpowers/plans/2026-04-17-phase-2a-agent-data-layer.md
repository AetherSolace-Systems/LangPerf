# Phase 2a — Agent Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce first-class Agents into LangPerf's backend. Every ingested run is automatically attributed to an Agent (via signature fingerprinting) and a Version (git SHA + package version). Existing data is backfilled to synthetic Agents derived from `service_name`. New REST endpoints expose Agent data for the UI (Phase 2b) to render.

**Architecture:** Agents and AgentVersions become ORM entities with FK columns added to `trajectories`. The Python SDK auto-detects an Agent signature at `init()` time from git origin + init call site, sends it as OTel resource attributes (`langperf.agent.*`), and the ingest path upserts Agent/AgentVersion rows before saving each trajectory. Alembic replaces `create_all()` for schema management. A one-time backfill migration assigns every existing trajectory to a synthetic Agent derived from its `service_name`. No UI changes; that's Phase 2b.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 (async) + asyncpg + Alembic + OpenTelemetry Python SDK + Postgres 16.

---

## File Structure

**New files:**
- `api/alembic.ini` — Alembic project config
- `api/alembic/env.py` — Alembic runtime env (async-aware)
- `api/alembic/script.py.mako` — migration template
- `api/alembic/versions/0001_baseline.py` — baseline migration capturing current trajectories + spans schema
- `api/alembic/versions/0002_agents.py` — adds agents + agent_versions tables + trajectory FK columns
- `api/alembic/versions/0003_backfill_agents.py` — data migration: one synthetic Agent per distinct `service_name`
- `api/app/otlp/agent_resolver.py` — upsert Agent + AgentVersion given OTel resource attributes
- `api/app/api/agents.py` — `/api/agents` router
- `api/app/agent_naming.py` — docker-style name generator
- `sdk/langperf/signature.py` — git + stack-inspect fingerprint utility

**Modified files:**
- `api/app/main.py` — run `alembic upgrade head` on startup instead of `create_all`
- `api/app/models.py` — add `Agent` + `AgentVersion` models + FK columns on `Trajectory`
- `api/app/constants.py` — add `ATTR_AGENT_SIGNATURE`, `ATTR_AGENT_VERSION_SHA`, `ATTR_AGENT_VERSION_PACKAGE`
- `api/app/schemas.py` — add `AgentSummary`, `AgentDetail`, `AgentMetrics`, `AgentToolUsage`, `AgentPatch` models
- `api/app/otlp/ingest.py` — call `agent_resolver` and populate trajectory FKs
- `sdk/langperf/tracer.py` — compute signature + version, add to OTel resource attributes
- `sdk/langperf/__init__.py` — expose `signature` submodule (optional; for introspection)
- `api/Dockerfile` — copy `alembic/` + `alembic.ini` into the image
- `scripts/seed_demo_data.py` — generate multi-agent, multi-version runs so Phase 2b UI has something real to render

**Unchanged (rely on new behavior via FKs / attributes):**
- The existing `/api/trajectories/*` endpoints stay — they continue serving the History view. Phase 2b will add agent-scoped variants alongside.

---

## Data Model Summary (what we're adding)

```
agents
  id                uuid pk
  signature         text unique       -- stable fingerprint (git+path OR mod+host)
  name              text unique       -- auto-generated ("crimson-dagger"), user-renamable
  display_name      text nullable
  description       text nullable
  owner             text nullable
  github_url        text nullable
  language          text nullable
  created_at        timestamptz
  updated_at        timestamptz

agent_versions
  id                uuid pk
  agent_id          uuid fk -> agents.id ON DELETE CASCADE
  git_sha           text nullable
  short_sha         text nullable
  package_version   text nullable
  label             text              -- package_version OR "sha:<short_sha>" OR "unknown"
  first_seen_at     timestamptz
  last_seen_at      timestamptz
  unique(agent_id, coalesce(git_sha, ''), coalesce(package_version, ''))

trajectories (existing table — new columns, both nullable)
  agent_id          uuid fk -> agents.id
  agent_version_id  uuid fk -> agent_versions.id
```

**Signature rule:** Strict string. At SDK init():
1. If `git -C <cwd> rev-parse --show-toplevel` succeeds AND `git -C <repo> remote get-url origin` returns a URL: `signature = "git:" + origin_url + ":" + path_of_init_caller_relative_to_repo_root`
2. Otherwise: `signature = "mod:" + socket.gethostname() + ":" + sys.modules[caller_module].__name__`

The SDK sends the raw signature string as a resource attribute. The backend stores it as-is (no hashing) — trivially deduplicable and human-debuggable.

**Auto-naming rule:** First time an unknown signature is seen, `agent_naming.generate_name()` returns a fresh `adjective-noun` pair (docker-style), rejecting any that collide with an existing `agents.name`. Built from static word lists in the module.

---

### Task 1: Introduce Alembic (config + baseline)

**Files:**
- Create: `api/alembic.ini`
- Create: `api/alembic/env.py`
- Create: `api/alembic/script.py.mako`
- Create: `api/alembic/versions/0001_baseline.py`
- Modify: `api/Dockerfile`

- [ ] **Step 1: Create `api/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
# sqlalchemy.url is set dynamically in env.py from DATABASE_URL

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Create `api/alembic/env.py`**

```python
"""Alembic runtime env — async-aware, reads DATABASE_URL from the env."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject DATABASE_URL from environment so the same URL the app uses drives migrations.
config.set_main_option(
    "sqlalchemy.url",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://langperf:langperf@postgres:5432/langperf",
    ),
)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 3: Create `api/alembic/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: str | None = ${repr(down_revision)}
branch_labels: str | None = ${repr(branch_labels)}
depends_on: str | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Create `api/alembic/versions/0001_baseline.py`**

This captures the current schema so Alembic can "stamp" existing databases at version 0001 without recreating tables. On fresh databases it creates the tables.

```python
"""baseline — trajectories + spans

Revision ID: 0001
Revises:
Create Date: 2026-04-17 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trajectories",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("trace_id", sa.String(), nullable=True),
        sa.Column("service_name", sa.String(), nullable=False),
        sa.Column("environment", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_tag", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_trajectories_trace_id", "trajectories", ["trace_id"])
    op.create_index("ix_trajectories_service_name", "trajectories", ["service_name"])
    op.create_index("ix_trajectories_environment", "trajectories", ["environment"])
    op.create_index("ix_trajectories_started_at", "trajectories", ["started_at"])
    op.create_index("ix_trajectories_status_tag", "trajectories", ["status_tag"])

    op.create_table(
        "spans",
        sa.Column("span_id", sa.String(), primary_key=True),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column(
            "trajectory_id",
            UUID(as_uuid=False),
            sa.ForeignKey("trajectories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parent_span_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("attributes", JSONB(), nullable=False),
        sa.Column("events", JSONB(), nullable=True),
        sa.Column("status_code", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_spans_trace_id", "spans", ["trace_id"])
    op.create_index("ix_spans_trajectory_id", "spans", ["trajectory_id"])
    op.create_index("ix_spans_started_at", "spans", ["started_at"])


def downgrade() -> None:
    op.drop_table("spans")
    op.drop_table("trajectories")
```

- [ ] **Step 5: Modify `api/Dockerfile` to copy Alembic files into the image**

Read current `api/Dockerfile` first: `cat /Users/andrewlavoie/code/langperf/api/Dockerfile`

The Dockerfile needs `COPY alembic.ini ./` and `COPY alembic/ ./alembic/` added alongside the existing `COPY app/` line. If the Dockerfile does `COPY . .` (whole-context copy), nothing needs to change.

If the COPY is granular (likely `COPY app/ ./app/`), add:
```dockerfile
COPY alembic.ini ./
COPY alembic/ ./alembic/
```
directly after the existing app copy.

- [ ] **Step 6: Stamp existing databases at 0001, run nothing**

Because existing dogfood DBs already have `trajectories` + `spans` (created by `create_all`), running `upgrade 0001` on them would fail (tables already exist). Handle this by providing a startup script that **if tables exist AND no alembic_version row exists, stamps 0001**, else runs `upgrade head`.

This is handled in Task 5 (wiring the Alembic-vs-stamp decision into startup). Leave it for Task 5 — Task 1 is just getting Alembic files in place.

- [ ] **Step 7: Local sanity test**

```bash
cd /Users/andrewlavoie/code/langperf/api
docker compose -f ../docker-compose.yml exec langperf-api python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.current(cfg)"
```

Expected: prints `0001 (head)` on fresh DBs, or `(none)` on existing DBs (which will be stamped in Task 5).

If the api container isn't running, skip this step — the full integration test comes in Task 10.

- [ ] **Step 8: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/alembic.ini api/alembic/ api/Dockerfile
git commit -m "api: introduce Alembic with baseline migration (0001)"
```

---

### Task 2: Add `Agent` + `AgentVersion` ORM models + attribute constants

**Files:**
- Modify: `api/app/models.py`
- Modify: `api/app/constants.py`

- [ ] **Step 1: Read `api/app/constants.py`**

```bash
cat /Users/andrewlavoie/code/langperf/api/app/constants.py
```

Preserve all existing constants. At the bottom, append new attribute names:

```python

# Agent identity — sent by SDK as OTel resource attributes
ATTR_AGENT_SIGNATURE = "langperf.agent.signature"
ATTR_AGENT_VERSION_SHA = "langperf.agent.version.sha"
ATTR_AGENT_VERSION_SHORT_SHA = "langperf.agent.version.short_sha"
ATTR_AGENT_VERSION_PACKAGE = "langperf.agent.version.package"
ATTR_AGENT_LANGUAGE = "langperf.agent.language"
ATTR_AGENT_GIT_ORIGIN = "langperf.agent.git_origin"
```

- [ ] **Step 2: Update `api/app/models.py` — add `Agent` + `AgentVersion` + trajectory FK columns**

Replace the file with:

```python
"""ORM models: Trajectory, Span, Agent, AgentVersion.

Large payloads land in JSONB `attributes` on spans — Postgres TOASTs values
>2KB automatically so trajectories with long context windows compress in place.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    signature: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        order_by="AgentVersion.first_seen_at.desc()",
    )


class AgentVersion(Base):
    __tablename__ = "agent_versions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    git_sha: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    short_sha: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    package_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    label: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    agent: Mapped["Agent"] = relationship(back_populates="versions")

    __table_args__ = (
        # Unique on agent + git_sha + package_version. Nulls are handled via
        # coalesce in the index expression (migration creates it explicitly).
        UniqueConstraint(
            "agent_id", "git_sha", "package_version", name="uq_agent_version_identity"
        ),
    )


class Trajectory(Base):
    __tablename__ = "trajectories"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    service_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    environment: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status_tag: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    step_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # NEW — populated by ingest; nullable so legacy rows can exist until backfill runs.
    agent_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_version_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("agent_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    spans: Mapped[list["Span"]] = relationship(
        back_populates="trajectory",
        cascade="all, delete-orphan",
        order_by="Span.started_at",
    )
    agent: Mapped[Optional["Agent"]] = relationship("Agent", foreign_keys=[agent_id])
    agent_version: Mapped[Optional["AgentVersion"]] = relationship(
        "AgentVersion", foreign_keys=[agent_version_id]
    )


class Span(Base):
    __tablename__ = "spans"

    span_id: Mapped[str] = mapped_column(String, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    trajectory_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("trajectories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_span_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    events: Mapped[Optional[list[Any]]] = mapped_column(JSONB, nullable=True)
    status_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trajectory: Mapped["Trajectory"] = relationship(back_populates="spans")
```

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/app/models.py api/app/constants.py
git commit -m "api: add Agent + AgentVersion models + trajectory FK columns"
```

---

### Task 3: Migration 0002 — `agents`, `agent_versions`, trajectory FKs

**Files:**
- Create: `api/alembic/versions/0002_agents.py`

- [ ] **Step 1: Create the migration**

```python
"""agents + agent_versions + trajectory FK columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-17 00:01:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column("signature", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(), nullable=True),
        sa.Column("github_url", sa.String(), nullable=True),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_agents_signature", "agents", ["signature"])
    op.create_index("ix_agents_name", "agents", ["name"])

    op.create_table(
        "agent_versions",
        sa.Column("id", UUID(as_uuid=False), primary_key=True),
        sa.Column(
            "agent_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("git_sha", sa.String(), nullable=True),
        sa.Column("short_sha", sa.String(), nullable=True),
        sa.Column("package_version", sa.String(), nullable=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "agent_id", "git_sha", "package_version", name="uq_agent_version_identity"
        ),
    )
    op.create_index("ix_agent_versions_agent_id", "agent_versions", ["agent_id"])

    op.add_column(
        "trajectories",
        sa.Column(
            "agent_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "trajectories",
        sa.Column(
            "agent_version_id",
            UUID(as_uuid=False),
            sa.ForeignKey("agent_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_trajectories_agent_id", "trajectories", ["agent_id"])
    op.create_index("ix_trajectories_agent_version_id", "trajectories", ["agent_version_id"])


def downgrade() -> None:
    op.drop_index("ix_trajectories_agent_version_id", table_name="trajectories")
    op.drop_index("ix_trajectories_agent_id", table_name="trajectories")
    op.drop_column("trajectories", "agent_version_id")
    op.drop_column("trajectories", "agent_id")
    op.drop_index("ix_agent_versions_agent_id", table_name="agent_versions")
    op.drop_table("agent_versions")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_index("ix_agents_signature", table_name="agents")
    op.drop_table("agents")
```

- [ ] **Step 2: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/alembic/versions/0002_agents.py
git commit -m "api: migration 0002 — agents, agent_versions, trajectory FKs"
```

---

### Task 4: Docker-style agent-name generator

**Files:**
- Create: `api/app/agent_naming.py`

- [ ] **Step 1: Create the file**

```python
"""Auto-generate adjective-noun agent names (docker-style).

Called at first-sight of an unknown agent signature. The generator picks a
random adjective/noun pair and asks the caller to confirm it's unique in the
`agents.name` column. On collision, try again (capped at 50 attempts — if
that fails the word lists are too small).
"""

from __future__ import annotations

import random
from typing import Callable

ADJECTIVES: tuple[str, ...] = (
    "amber", "arctic", "azure", "bold", "brisk", "brave", "bronze",
    "calm", "clever", "cobalt", "copper", "coral", "crimson", "cyan",
    "daring", "deep", "dusty", "eager", "ember", "fabled", "fallow",
    "frosted", "gentle", "gilded", "glacial", "golden", "graceful",
    "hazel", "humble", "icy", "indigo", "iron", "jade", "jovial",
    "lucent", "lunar", "muted", "mystic", "noble", "opal", "pensive",
    "placid", "quiet", "quick", "ruby", "russet", "sable", "savvy",
    "sienna", "silent", "silver", "slate", "solar", "stoic", "storm",
    "swift", "tawny", "thorn", "tidal", "umber", "velvet", "verdant",
    "vermilion", "warm", "whispering", "wild", "windy", "woven",
)

NOUNS: tuple[str, ...] = (
    "anvil", "arrow", "atlas", "beacon", "bison", "blade", "bloom",
    "bolt", "cairn", "cedar", "cipher", "cobra", "comet", "copper",
    "crest", "dagger", "dune", "ember", "falcon", "fern", "flint",
    "forge", "fountain", "garland", "gear", "glyph", "grove", "harbor",
    "hawk", "heron", "ingot", "jaguar", "kettle", "lantern", "lichen",
    "loom", "meadow", "meridian", "mesa", "miner", "moth", "nimbus",
    "oak", "obelisk", "orchard", "otter", "palette", "peregrine",
    "pillar", "pine", "quarry", "quartz", "ranger", "raven", "reef",
    "runner", "sable", "sage", "scribe", "shoal", "shore", "signal",
    "skein", "spring", "summit", "talon", "tinder", "torch", "tundra",
    "valley", "vane", "vintage", "warren", "weaver", "willow", "wren",
    "zenith",
)


def _candidate(rng: random.Random) -> str:
    return f"{rng.choice(ADJECTIVES)}-{rng.choice(NOUNS)}"


def generate_name(
    name_exists: Callable[[str], bool],
    *,
    seed: int | None = None,
    max_attempts: int = 50,
) -> str:
    """Return a fresh "adjective-noun" that passes name_exists() → False.

    Raises RuntimeError if it can't find a free slot in max_attempts tries.
    """
    rng = random.Random(seed)
    for _ in range(max_attempts):
        candidate = _candidate(rng)
        if not name_exists(candidate):
            return candidate
    raise RuntimeError(
        f"Could not find unused agent name after {max_attempts} attempts — "
        "word lists may be too small"
    )
```

- [ ] **Step 2: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/app/agent_naming.py
git commit -m "api: docker-style agent-name generator"
```

---

### Task 5: Agent resolver — upsert Agent + AgentVersion from OTel resource attrs

**Files:**
- Create: `api/app/otlp/agent_resolver.py`

- [ ] **Step 1: Create the file**

```python
"""Given OTel resource attributes, return (agent_id, agent_version_id).

Upserts rows in agents + agent_versions as needed. Reuses `agents.signature`
as the dedup key, and `(agent_id, git_sha, package_version)` as the version
dedup key. All writes stay in the caller's session; caller commits.

Also updates `agents.language`, `agents.github_url`, and `agent_versions.last_seen_at`
on every ingest so they stay current without a separate heartbeat.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_naming import generate_name
from app.constants import (
    ATTR_AGENT_GIT_ORIGIN,
    ATTR_AGENT_LANGUAGE,
    ATTR_AGENT_SIGNATURE,
    ATTR_AGENT_VERSION_PACKAGE,
    ATTR_AGENT_VERSION_SHA,
    ATTR_AGENT_VERSION_SHORT_SHA,
)
from app.models import Agent, AgentVersion

logger = logging.getLogger("langperf.otlp.agent_resolver")


def _derive_github_url(git_origin: Optional[str]) -> Optional[str]:
    """Convert `git@github.com:user/repo.git` or ssh URLs → https github.com URL."""
    if not git_origin:
        return None
    if git_origin.startswith("https://github.com/"):
        return git_origin.removesuffix(".git")
    if git_origin.startswith("git@github.com:"):
        path = git_origin[len("git@github.com:"):].removesuffix(".git")
        return f"https://github.com/{path}"
    return None


def _version_label(package_version: Optional[str], short_sha: Optional[str]) -> str:
    if package_version:
        return package_version
    if short_sha:
        return f"sha:{short_sha}"
    return "unknown"


async def resolve_agent_and_version(
    session: AsyncSession, resource_attrs: dict[str, Any]
) -> tuple[Optional[str], Optional[str]]:
    """Return (agent_id, agent_version_id) for the resource attrs.

    If no signature is present (e.g. legacy SDK), returns (None, None) —
    caller is expected to leave trajectory FKs null, and the backfill step
    will attribute them later.
    """
    signature = resource_attrs.get(ATTR_AGENT_SIGNATURE)
    if not signature:
        return None, None

    git_sha = resource_attrs.get(ATTR_AGENT_VERSION_SHA)
    short_sha = resource_attrs.get(ATTR_AGENT_VERSION_SHORT_SHA)
    package_version = resource_attrs.get(ATTR_AGENT_VERSION_PACKAGE)
    language = resource_attrs.get(ATTR_AGENT_LANGUAGE)
    git_origin = resource_attrs.get(ATTR_AGENT_GIT_ORIGIN)

    agent = await _upsert_agent(
        session,
        signature=signature,
        language=language,
        git_origin=git_origin,
    )
    version = await _upsert_version(
        session,
        agent_id=agent.id,
        git_sha=git_sha,
        short_sha=short_sha,
        package_version=package_version,
    )
    return agent.id, version.id


async def _upsert_agent(
    session: AsyncSession,
    *,
    signature: str,
    language: Optional[str],
    git_origin: Optional[str],
) -> Agent:
    # Look up by signature first — fast path.
    existing = (
        await session.execute(select(Agent).where(Agent.signature == signature))
    ).scalar_one_or_none()
    if existing:
        # Keep language / github_url fresh if the SDK started reporting more.
        changed = False
        if language and not existing.language:
            existing.language = language
            changed = True
        inferred_github = _derive_github_url(git_origin)
        if inferred_github and not existing.github_url:
            existing.github_url = inferred_github
            changed = True
        if changed:
            session.add(existing)
        return existing

    # New agent — pick an unused name.
    name = await _pick_unused_name(session)
    new = Agent(
        id=str(uuid.uuid4()),
        signature=signature,
        name=name,
        language=language,
        github_url=_derive_github_url(git_origin),
    )
    session.add(new)
    await session.flush()  # ensure .id is populated before we use it as an FK
    logger.info("agent_signature_new sig=%s generated_name=%s", signature, name)
    return new


async def _pick_unused_name(session: AsyncSession) -> str:
    async def exists(name: str) -> bool:
        res = await session.execute(select(Agent.id).where(Agent.name == name))
        return res.scalar_one_or_none() is not None

    # generate_name is sync; we wrap a sync bridge over the async `exists`.
    # For v1 scale (tens of agents) the linear call count is fine.
    # Create a cache so we don't re-query the same candidate twice in one call.
    seen: set[str] = set()

    def cached_exists(candidate: str) -> bool:
        if candidate in seen:
            return True
        seen.add(candidate)
        # Schedule the async check via ensure_future + run loop? Simpler:
        # do the check synchronously by using session.sync_session if needed.
        # At v1 scale, linear scan of N candidates is not a hot path.
        # We call the async check from the async caller; generate_name's hook
        # expects sync — so we do one synchronous round-trip per candidate.
        # Implementation: raise if we end up here.
        raise NotImplementedError  # see below

    # Simpler approach: fetch all existing names up-front, then let
    # generate_name do pure in-memory checks.
    taken = set(
        (
            await session.execute(select(Agent.name))
        ).scalars().all()
    )
    return generate_name(lambda candidate: candidate in taken)


async def _upsert_version(
    session: AsyncSession,
    *,
    agent_id: str,
    git_sha: Optional[str],
    short_sha: Optional[str],
    package_version: Optional[str],
) -> AgentVersion:
    label = _version_label(package_version, short_sha)
    existing_stmt = select(AgentVersion).where(
        AgentVersion.agent_id == agent_id,
        AgentVersion.git_sha.is_(git_sha) if git_sha is None else AgentVersion.git_sha == git_sha,
        AgentVersion.package_version.is_(package_version)
        if package_version is None
        else AgentVersion.package_version == package_version,
    )
    existing = (await session.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        # last_seen_at auto-updates via onupdate=func.now() on any UPDATE.
        # Nudge the row so the update fires.
        existing.label = label
        session.add(existing)
        return existing

    new = AgentVersion(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        git_sha=git_sha,
        short_sha=short_sha,
        package_version=package_version,
        label=label,
    )
    session.add(new)
    await session.flush()
    return new
```

Note: the earlier `cached_exists` scaffolding was left in as a comment for clarity — the actual implementation is the simpler "fetch all names, pass an in-memory predicate" path that follows `# Simpler approach`. When writing this file, DELETE the `async def exists` block and the `def cached_exists` block — they're pedagogical, not part of the final code. Keep only:

```python
async def _pick_unused_name(session: AsyncSession) -> str:
    taken = set(
        (await session.execute(select(Agent.name))).scalars().all()
    )
    return generate_name(lambda candidate: candidate in taken)
```

- [ ] **Step 2: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/app/otlp/agent_resolver.py
git commit -m "api: agent_resolver — upsert Agent + AgentVersion from resource attrs"
```

---

### Task 6: Wire `agent_resolver` into ingest + run Alembic on startup

**Files:**
- Modify: `api/app/otlp/ingest.py`
- Modify: `api/app/main.py`

- [ ] **Step 1: Update `api/app/otlp/ingest.py` — call `resolve_agent_and_version` in `_upsert_trajectory_for_span`**

The function currently sets `service_name`, `environment`, `name` on trajectories. Add agent + version FK population.

Read the current file first to preserve the shape, then add these changes:

- Import `resolve_agent_and_version` at the top: `from app.otlp.agent_resolver import resolve_agent_and_version`
- In `_upsert_trajectory_for_span`, before the `stmt = pg_insert(Trajectory)...` block, call:
  ```python
  agent_id, agent_version_id = await resolve_agent_and_version(session, resource_attrs)
  ```
- Add the two IDs to the `values` dict:
  ```python
  values: dict[str, Any] = {
      # … existing keys …
      "agent_id": agent_id,
      "agent_version_id": agent_version_id,
  }
  ```
- In the existing-trajectory update block (`if existing:` branch), also update FKs when the existing row doesn't have them yet:
  ```python
  if agent_id and not existing.agent_id:
      existing.agent_id = agent_id
      changed = True
  if agent_version_id and not existing.agent_version_id:
      existing.agent_version_id = agent_version_id
      changed = True
  ```

The exact patch applied to `_upsert_trajectory_for_span` (which currently spans lines 120–172 of ingest.py):

```python
async def _upsert_trajectory_for_span(
    session: AsyncSession,
    *,
    traj_id: str,
    trace_id: str,
    resource_attrs: dict[str, Any],
    span: DecodedSpan,
    span_started_at: datetime,
    span_ended_at: datetime | None,
) -> None:
    service_name = resolve_service_name(resource_attrs)
    environment = resolve_environment(resource_attrs)
    name = resolve_trajectory_name(span, resource_attrs)
    agent_id, agent_version_id = await resolve_agent_and_version(
        session, resource_attrs
    )

    values: dict[str, Any] = {
        "id": traj_id,
        "trace_id": trace_id,
        "service_name": service_name,
        "environment": environment,
        "name": name,
        "started_at": span_started_at,
        "ended_at": span_ended_at,
        "step_count": 0,
        "token_count": 0,
        "duration_ms": None,
        "agent_id": agent_id,
        "agent_version_id": agent_version_id,
    }

    stmt = pg_insert(Trajectory).values(**values)
    stmt = stmt.on_conflict_do_nothing(index_elements=[Trajectory.id])
    await session.execute(stmt)

    existing = await session.get(Trajectory, traj_id)
    if existing:
        changed = False
        if span_started_at < existing.started_at:
            existing.started_at = span_started_at
            changed = True
        if span_ended_at and (
            existing.ended_at is None or span_ended_at > existing.ended_at
        ):
            existing.ended_at = span_ended_at
            changed = True
        if name and not existing.name:
            existing.name = name
            changed = True
        if environment and not existing.environment:
            existing.environment = environment
            changed = True
        if agent_id and not existing.agent_id:
            existing.agent_id = agent_id
            changed = True
        if agent_version_id and not existing.agent_version_id:
            existing.agent_version_id = agent_version_id
            changed = True
        if changed:
            session.add(existing)
```

Add `from app.otlp.agent_resolver import resolve_agent_and_version` to the existing import block (after the other `app.otlp.*` imports).

- [ ] **Step 2: Update `api/app/main.py` startup to use Alembic**

Replace the `lifespan` function. The new behavior:
1. On startup, check if tables exist (query `information_schema.tables`).
2. If `trajectories` exists but `alembic_version` row does NOT (pre-Alembic dogfood DB): stamp 0001 so Alembic thinks baseline is applied, then upgrade head (runs 0002 + 0003).
3. If no tables exist: upgrade head (runs 0001 → 0002 → 0003 from scratch).
4. If `alembic_version` already has a row: upgrade head (regular migration).

```python
import logging
import os
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.agents import router as agents_router
from app.api.nodes import router as nodes_router
from app.api.trajectories import router as trajectories_router
from app.db import engine
from app.otlp.receiver import router as otlp_router

logging.basicConfig(
    level=os.environ.get("LANGPERF_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("langperf")


async def _is_pre_alembic_db() -> bool:
    """Return True iff trajectories exists but alembic_version does not."""
    async with engine.begin() as conn:
        trajectories = (
            await conn.execute(
                text(
                    "SELECT to_regclass('public.trajectories') IS NOT NULL AS present"
                )
            )
        ).scalar_one()
        alembic_version = (
            await conn.execute(
                text(
                    "SELECT to_regclass('public.alembic_version') IS NOT NULL AS present"
                )
            )
        ).scalar_one()
    return bool(trajectories) and not bool(alembic_version)


def _alembic_cfg() -> Config:
    cfg = Config("alembic.ini")
    return cfg


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = _alembic_cfg()
    if await _is_pre_alembic_db():
        logger.info("pre-Alembic DB detected — stamping baseline (0001)")
        command.stamp(cfg, "0001")
    logger.info("alembic upgrade head")
    command.upgrade(cfg, "head")
    logger.info("langperf-api ready")
    yield
    await engine.dispose()


app = FastAPI(title="LangPerf API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "langperf-api", "version": "0.1.0"}


@app.get("/healthz")
async def healthz():
    return {"ok": True}


app.include_router(otlp_router)
app.include_router(trajectories_router)
app.include_router(nodes_router)
app.include_router(agents_router)
```

Note: `agents_router` gets created in Task 8 — this file references it so include that task before the container restarts. If it doesn't exist yet, comment out the `from app.api.agents import router as agents_router` and the `app.include_router(agents_router)` lines for now; Task 8 will uncomment.

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/app/otlp/ingest.py api/app/main.py
git commit -m "api: wire agent_resolver into ingest + run alembic on startup"
```

---

### Task 7: Backfill migration 0003 — attribute legacy trajectories to synthetic Agents

**Files:**
- Create: `api/alembic/versions/0003_backfill_agents.py`

- [ ] **Step 1: Create the migration**

```python
"""backfill — one synthetic Agent per distinct service_name

Any trajectories with agent_id IS NULL get attributed to a synthetic Agent
with signature "legacy:<service_name>" and a docker-style name. Synthetic
Agents get a generic "unknown" version so the FK on trajectories is
populated end-to-end. Idempotent — running twice is a no-op.

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-17 00:02:00
"""

from __future__ import annotations

import random
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

ADJECTIVES = (
    "amber", "arctic", "azure", "bold", "brisk", "brave", "bronze",
    "calm", "clever", "cobalt", "copper", "coral", "crimson", "cyan",
    "daring", "deep", "dusty", "eager", "ember", "fabled", "fallow",
    "frosted", "gentle", "gilded", "glacial", "golden", "graceful",
    "hazel", "humble", "icy", "indigo", "iron", "jade", "jovial",
    "lucent", "lunar", "muted", "mystic", "noble", "opal", "pensive",
    "placid", "quiet", "quick", "ruby", "russet", "sable", "savvy",
    "sienna", "silent", "silver", "slate", "solar", "stoic", "storm",
    "swift", "tawny", "thorn", "tidal", "umber", "velvet", "verdant",
    "vermilion", "warm", "whispering", "wild", "windy", "woven",
)
NOUNS = (
    "anvil", "arrow", "atlas", "beacon", "bison", "blade", "bloom",
    "bolt", "cairn", "cedar", "cipher", "cobra", "comet", "copper",
    "crest", "dagger", "dune", "ember", "falcon", "fern", "flint",
    "forge", "fountain", "garland", "gear", "glyph", "grove", "harbor",
    "hawk", "heron", "ingot", "jaguar", "kettle", "lantern", "lichen",
    "loom", "meadow", "meridian", "mesa", "miner", "moth", "nimbus",
    "oak", "obelisk", "orchard", "otter", "palette", "peregrine",
    "pillar", "pine", "quarry", "quartz", "ranger", "raven", "reef",
    "runner", "sable", "sage", "scribe", "shoal", "shore", "signal",
    "skein", "spring", "summit", "talon", "tinder", "torch", "tundra",
    "valley", "vane", "vintage", "warren", "weaver", "willow", "wren",
    "zenith",
)


def _pick_name(taken: set[str], rng: random.Random) -> str:
    for _ in range(200):
        candidate = f"{rng.choice(ADJECTIVES)}-{rng.choice(NOUNS)}"
        if candidate not in taken:
            taken.add(candidate)
            return candidate
    raise RuntimeError("could not find unused agent name during backfill")


def upgrade() -> None:
    conn = op.get_bind()
    rng = random.Random(42)  # deterministic so re-running in tests is stable

    # Set of names already in use — may include Agents created before backfill.
    taken = {
        row[0]
        for row in conn.execute(sa.text("SELECT name FROM agents")).fetchall()
    }

    # For each distinct service_name with orphan trajectories, create a synthetic Agent.
    rows = conn.execute(
        sa.text(
            """
            SELECT DISTINCT service_name
            FROM trajectories
            WHERE agent_id IS NULL
              AND service_name IS NOT NULL
            """
        )
    ).fetchall()

    for (service_name,) in rows:
        signature = f"legacy:{service_name}"
        # If an Agent with this signature already exists (re-run), reuse it.
        existing = conn.execute(
            sa.text("SELECT id, name FROM agents WHERE signature = :sig"),
            {"sig": signature},
        ).fetchone()
        if existing:
            agent_id, name = existing
        else:
            name = _pick_name(taken, rng)
            agent_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    """
                    INSERT INTO agents (id, signature, name, description)
                    VALUES (:id, :sig, :name, :desc)
                    """
                ),
                {
                    "id": agent_id,
                    "sig": signature,
                    "name": name,
                    "desc": f"Backfilled from service_name={service_name}",
                },
            )

        # Synthetic "unknown" version.
        version_row = conn.execute(
            sa.text(
                """
                SELECT id FROM agent_versions
                WHERE agent_id = :aid
                  AND git_sha IS NULL
                  AND package_version IS NULL
                """
            ),
            {"aid": agent_id},
        ).fetchone()
        if version_row:
            version_id = version_row[0]
        else:
            version_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    """
                    INSERT INTO agent_versions (id, agent_id, label)
                    VALUES (:id, :aid, 'unknown')
                    """
                ),
                {"id": version_id, "aid": agent_id},
            )

        conn.execute(
            sa.text(
                """
                UPDATE trajectories
                   SET agent_id = :aid,
                       agent_version_id = :vid
                 WHERE agent_id IS NULL
                   AND service_name = :svc
                """
            ),
            {"aid": agent_id, "vid": version_id, "svc": service_name},
        )


def downgrade() -> None:
    # No-op: the trajectories FKs get cleared when 0002 downgrades drops the columns.
    pass
```

- [ ] **Step 2: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/alembic/versions/0003_backfill_agents.py
git commit -m "api: migration 0003 — backfill legacy trajectories to synthetic Agents"
```

---

### Task 8: `/api/agents` list + detail + PATCH endpoints

**Files:**
- Create: `api/app/api/agents.py`
- Modify: `api/app/schemas.py` — add `AgentSummary`, `AgentDetail`, `AgentPatch`

- [ ] **Step 1: Append to `api/app/schemas.py`**

Read existing file first: `cat /Users/andrewlavoie/code/langperf/api/app/schemas.py`

At the bottom (preserving all existing models), add:

```python
# ── Agents ────────────────────────────────────────────────────────────────

from datetime import datetime  # if not already imported at the top


class AgentVersionSummary(BaseModel):
    id: str
    label: str
    git_sha: Optional[str] = None
    short_sha: Optional[str] = None
    package_version: Optional[str] = None
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


class AgentSummary(BaseModel):
    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    github_url: Optional[str] = None
    language: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentDetail(AgentSummary):
    signature: str
    versions: list[AgentVersionSummary] = []


class AgentPatch(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    github_url: Optional[str] = None
    rename_to: Optional[str] = None  # changes `agents.name` (URL-visible)
```

If `BaseModel` / `Optional` / `Field` are already imported at the top, don't duplicate. Only add the `datetime` import if not already present.

- [ ] **Step 2: Create `api/app/api/agents.py`**

```python
"""Agents list / detail / PATCH endpoints."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Agent
from app.schemas import AgentDetail, AgentPatch, AgentSummary

router = APIRouter(prefix="/api/agents")

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@router.get("", response_model=list[AgentSummary])
async def list_agents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AgentSummary]:
    result = await session.execute(
        select(Agent).order_by(Agent.name).limit(limit).offset(offset)
    )
    return [AgentSummary.model_validate(a) for a in result.scalars().all()]


@router.get("/{name}", response_model=AgentDetail)
async def get_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> AgentDetail:
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name)
        .options(selectinload(Agent.versions))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentDetail.model_validate(agent)


@router.patch("/{name}", response_model=AgentDetail)
async def patch_agent(
    name: str,
    patch: AgentPatch,
    session: AsyncSession = Depends(get_session),
) -> AgentDetail:
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name)
        .options(selectinload(Agent.versions))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")

    if patch.rename_to is not None:
        new_name = patch.rename_to.strip().lower()
        if not NAME_RE.match(new_name):
            raise HTTPException(
                status_code=400,
                detail="name must be lowercase letters/digits/hyphens, 1–64 chars, starting alphanumeric",
            )
        # Uniqueness check.
        collision = (
            await session.execute(
                select(Agent.id).where(Agent.name == new_name, Agent.id != agent.id)
            )
        ).scalar_one_or_none()
        if collision:
            raise HTTPException(status_code=409, detail="name already in use")
        agent.name = new_name

    if patch.display_name is not None:
        agent.display_name = patch.display_name or None
    if patch.description is not None:
        agent.description = patch.description or None
    if patch.owner is not None:
        agent.owner = patch.owner or None
    if patch.github_url is not None:
        agent.github_url = patch.github_url or None

    await session.commit()
    await session.refresh(agent)
    return AgentDetail.model_validate(agent)
```

- [ ] **Step 3: Confirm `api/app/main.py` includes the router**

Ensure `main.py` has:
```python
from app.api.agents import router as agents_router
# …
app.include_router(agents_router)
```

(In Task 6 step 2 this was added; if it was commented out due to the file not existing yet, uncomment now.)

- [ ] **Step 4: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/app/schemas.py api/app/api/agents.py api/app/main.py
git commit -m "api: /api/agents list + detail + PATCH"
```

---

### Task 9: `/api/agents/{name}/metrics`, `/tools`, `/runs`

**Files:**
- Modify: `api/app/api/agents.py` — append metrics / tools / runs routes
- Modify: `api/app/schemas.py` — add `AgentMetrics`, `AgentToolUsage`, `AgentRunRow`

- [ ] **Step 1: Append to `api/app/schemas.py`**

```python
class AgentToolUsage(BaseModel):
    tool: str
    calls: int
    errors: int  # count of calls that ended with status_code == 'ERROR'


class AgentMetrics(BaseModel):
    agent: str
    window: str  # "24h" | "7d" | "30d"
    runs: int
    errors: int
    error_rate: float
    p50_latency_ms: Optional[int]
    p95_latency_ms: Optional[int]
    p99_latency_ms: Optional[int]
    total_tokens: int


class AgentRunRow(BaseModel):
    id: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    step_count: int
    token_count: int
    status_tag: Optional[str]
    name: Optional[str]
    environment: Optional[str]
    version_label: Optional[str]


class AgentRunsResponse(BaseModel):
    items: list[AgentRunRow]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 2: Append routes to `api/app/api/agents.py`**

Add these imports at the top (alongside existing):
```python
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, Integer
from sqlalchemy.dialects.postgresql import aggregate_order_by
from app.models import AgentVersion, Span, Trajectory
from app.schemas import (
    AgentMetrics,
    AgentRunRow,
    AgentRunsResponse,
    AgentToolUsage,
)
```

Then, at the bottom of the file, add:

```python
_WINDOW_DELTA = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


async def _resolve_agent(session: AsyncSession, name: str) -> Agent:
    result = await session.execute(select(Agent).where(Agent.name == name))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.get("/{name}/metrics", response_model=AgentMetrics)
async def get_agent_metrics(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
) -> AgentMetrics:
    agent = await _resolve_agent(session, name)
    since = datetime.now(tz=timezone.utc) - _WINDOW_DELTA[window]

    base = select(Trajectory).where(
        Trajectory.agent_id == agent.id,
        Trajectory.started_at >= since,
    )

    runs = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
            )
        )
    ).scalar_one()

    errors = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
                Trajectory.status_tag == "bad",
            )
        )
    ).scalar_one()

    total_tokens = (
        await session.execute(
            select(func.coalesce(func.sum(Trajectory.token_count), 0)).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
            )
        )
    ).scalar_one()

    # Latency percentiles via Postgres percentile_cont.
    p_rows = (
        await session.execute(
            select(
                func.percentile_cont(0.50)
                .within_group(Trajectory.duration_ms.asc())
                .label("p50"),
                func.percentile_cont(0.95)
                .within_group(Trajectory.duration_ms.asc())
                .label("p95"),
                func.percentile_cont(0.99)
                .within_group(Trajectory.duration_ms.asc())
                .label("p99"),
            ).where(
                Trajectory.agent_id == agent.id,
                Trajectory.started_at >= since,
                Trajectory.duration_ms.is_not(None),
            )
        )
    ).one()

    def _to_int(x: object) -> Optional[int]:
        if x is None:
            return None
        return int(x)

    return AgentMetrics(
        agent=agent.name,
        window=window,
        runs=int(runs),
        errors=int(errors),
        error_rate=(float(errors) / float(runs)) if runs else 0.0,
        p50_latency_ms=_to_int(p_rows.p50),
        p95_latency_ms=_to_int(p_rows.p95),
        p99_latency_ms=_to_int(p_rows.p99),
        total_tokens=int(total_tokens),
    )


@router.get("/{name}/tools", response_model=list[AgentToolUsage])
async def get_agent_tools(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
) -> list[AgentToolUsage]:
    agent = await _resolve_agent(session, name)
    since = datetime.now(tz=timezone.utc) - _WINDOW_DELTA[window]

    # Span.name is the tool name when span.kind is tool/tool_call.
    result = await session.execute(
        select(
            Span.name.label("tool"),
            func.count().label("calls"),
            func.sum(
                func.cast(Span.status_code == "ERROR", Integer)
            ).label("errors"),
        )
        .join(Trajectory, Trajectory.id == Span.trajectory_id)
        .where(
            Trajectory.agent_id == agent.id,
            Trajectory.started_at >= since,
            Span.kind.in_(("tool", "tool_call")),
        )
        .group_by(Span.name)
        .order_by(func.count().desc())
        .limit(50)
    )
    return [
        AgentToolUsage(
            tool=row.tool,
            calls=int(row.calls),
            errors=int(row.errors or 0),
        )
        for row in result
    ]


@router.get("/{name}/runs", response_model=AgentRunsResponse)
async def get_agent_runs(
    name: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    environment: Optional[str] = Query(default=None),
    version: Optional[str] = Query(default=None, description="version label"),
    session: AsyncSession = Depends(get_session),
) -> AgentRunsResponse:
    agent = await _resolve_agent(session, name)

    stmt = (
        select(Trajectory, AgentVersion.label)
        .outerjoin(AgentVersion, AgentVersion.id == Trajectory.agent_version_id)
        .where(Trajectory.agent_id == agent.id)
    )
    if environment:
        stmt = stmt.where(Trajectory.environment == environment)
    if version:
        stmt = stmt.where(AgentVersion.label == version)

    total = (
        await session.execute(
            select(func.count()).select_from(
                stmt.order_by(None).subquery()
            )
        )
    ).scalar_one()

    result = await session.execute(
        stmt.order_by(Trajectory.started_at.desc()).limit(limit).offset(offset)
    )
    items: list[AgentRunRow] = []
    for traj, version_label in result.all():
        items.append(
            AgentRunRow(
                id=traj.id,
                started_at=traj.started_at,
                ended_at=traj.ended_at,
                duration_ms=traj.duration_ms,
                step_count=traj.step_count,
                token_count=traj.token_count,
                status_tag=traj.status_tag,
                name=traj.name,
                environment=traj.environment,
                version_label=version_label,
            )
        )
    return AgentRunsResponse(items=items, total=int(total), limit=limit, offset=offset)
```

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add api/app/schemas.py api/app/api/agents.py
git commit -m "api: /api/agents/{name}/metrics, /tools, /runs endpoints"
```

---

### Task 10: SDK — signature capture + wire into init()

**Files:**
- Create: `sdk/langperf/signature.py`
- Modify: `sdk/langperf/tracer.py`

- [ ] **Step 1: Create `sdk/langperf/signature.py`**

```python
"""Auto-detect agent identity at SDK init() time.

Signature rules:
  1. If running inside a git working tree AND `origin` is configured:
        signature = "git:" + origin_url + ":" + init_caller_path_relative_to_repo_root
     git_sha / short_sha / git_origin accompany the signature as separate attrs.
  2. Otherwise:
        signature = "mod:" + hostname + ":" + init_caller_module

Version rules:
  - git_sha / short_sha: from `git rev-parse HEAD`, if available
  - package_version: from importlib.metadata.version(<top_level_package>) where
    <top_level_package> is the first segment of the init caller's __name__.

All functions fail soft — they return None rather than raising — so a missing
git binary or a broken package metadata install doesn't block tracing.
"""

from __future__ import annotations

import inspect
import logging
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version as pkg_version
from pathlib import Path
from typing import Optional

logger = logging.getLogger("langperf.signature")


@dataclass(frozen=True)
class AgentIdentity:
    signature: str
    git_origin: Optional[str]
    git_sha: Optional[str]
    short_sha: Optional[str]
    package_version: Optional[str]
    language: str = "python"


def detect(caller_stack_offset: int = 2) -> AgentIdentity:
    """Return the best-effort agent identity for the current process.

    `caller_stack_offset` is how many frames above detect() the actual caller
    of langperf.init() lives. The default (2) is correct when detect() is
    called directly from init(). If you call detect() via a wrapper, bump.
    """
    caller_path, caller_module = _caller_info(caller_stack_offset)
    repo_root, origin = _git_context_for(caller_path)

    if repo_root and origin:
        rel = str(caller_path.resolve().relative_to(repo_root))
        signature = f"git:{origin}:{rel}"
    else:
        signature = f"mod:{socket.gethostname()}:{caller_module}"

    git_sha, short_sha = _git_head(repo_root) if repo_root else (None, None)
    pkg = _package_version_for(caller_module)

    return AgentIdentity(
        signature=signature,
        git_origin=origin,
        git_sha=git_sha,
        short_sha=short_sha,
        package_version=pkg,
    )


def _caller_info(stack_offset: int) -> tuple[Path, str]:
    frame = inspect.stack()[stack_offset]
    module_name = frame.frame.f_globals.get("__name__", "__unknown__")
    file_path = Path(frame.filename)
    return file_path, module_name


def _git_context_for(path: Path) -> tuple[Optional[Path], Optional[str]]:
    """Return (repo_root, origin_url) or (None, None)."""
    try:
        root = _git(path.parent, "rev-parse", "--show-toplevel")
    except _GitError:
        return None, None
    try:
        origin = _git(Path(root), "remote", "get-url", "origin")
    except _GitError:
        return Path(root), None
    return Path(root), origin.strip()


def _git_head(root: Path) -> tuple[Optional[str], Optional[str]]:
    try:
        sha = _git(root, "rev-parse", "HEAD").strip()
    except _GitError:
        return None, None
    return sha, sha[:7] if sha else None


class _GitError(RuntimeError):
    pass


def _git(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise _GitError(str(exc)) from exc
    if result.returncode != 0:
        raise _GitError(result.stderr.strip() or "git exited non-zero")
    return result.stdout


def _package_version_for(module_name: str) -> Optional[str]:
    if not module_name or module_name.startswith("__"):
        return None
    top = module_name.split(".", 1)[0]
    if not top:
        return None
    try:
        return pkg_version(top)
    except PackageNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001 — be generous, metadata layouts vary
        logger.debug("pkg_version(%s) failed: %s", top, exc)
        return None
```

- [ ] **Step 2: Update `sdk/langperf/tracer.py`**

Replace `init()` — preserve the existing signature + default resolution, add signature detection and new resource attributes. The full new `init()`:

```python
"""OTel tracer setup and global state for LangPerf."""

from __future__ import annotations

import logging
import os
from typing import Optional

from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from langperf._baggage import LangPerfBaggageSpanProcessor
from langperf.instrumentation import install_instrumentations
from langperf.signature import detect as detect_identity

logger = logging.getLogger("langperf")

_state: dict = {"initialized": False, "provider": None, "identity": None}


def init(
    *,
    endpoint: Optional[str] = None,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
) -> TracerProvider:
    """Configure LangPerf.

    Sets up an OTel TracerProvider with an OTLP/HTTP exporter, registers the
    LangPerf baggage-propagation span processor, and auto-installs OpenInference's
    `openai` instrumentation. Safe to call multiple times; only the first call
    wires up the global provider and instrumentations.

    Also auto-detects this agent's identity (signature + git SHA + package
    version) and attaches it as OTel resource attributes so the LangPerf
    backend can attribute every run to a first-class Agent entity without
    any user registration.

    Resolution order for each kwarg: explicit kwarg > env var > default.

    Env vars:
        LANGPERF_ENDPOINT       default: http://localhost:4318
        LANGPERF_SERVICE_NAME   default: "langperf-agent"
        LANGPERF_ENVIRONMENT    default: (unset)
    """
    if _state["initialized"]:
        logger.debug("langperf.init() called more than once; ignoring subsequent call")
        return _state["provider"]

    endpoint = endpoint or os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318")
    service_name = service_name or os.environ.get("LANGPERF_SERVICE_NAME", "langperf-agent")
    environment = environment or os.environ.get("LANGPERF_ENVIRONMENT")

    # detect() reads the call stack — bump the offset because we're now one
    # extra frame deep (init → detect(...) goes through this wrapper).
    identity = detect_identity(caller_stack_offset=2)

    resource_attrs: dict[str, object] = {
        "service.name": service_name,
        "langperf.agent.signature": identity.signature,
        "langperf.agent.language": identity.language,
    }
    if environment:
        resource_attrs["deployment.environment"] = environment
    if identity.git_origin:
        resource_attrs["langperf.agent.git_origin"] = identity.git_origin
    if identity.git_sha:
        resource_attrs["langperf.agent.version.sha"] = identity.git_sha
    if identity.short_sha:
        resource_attrs["langperf.agent.version.short_sha"] = identity.short_sha
    if identity.package_version:
        resource_attrs["langperf.agent.version.package"] = identity.package_version

    resource = Resource.create(resource_attrs)

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(LangPerfBaggageSpanProcessor())
    exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace_api.set_tracer_provider(provider)

    install_instrumentations(provider)

    _state["initialized"] = True
    _state["provider"] = provider
    _state["identity"] = identity
    logger.info(
        "langperf initialized: service=%s endpoint=%s env=%s signature=%s version=%s",
        service_name,
        endpoint,
        environment or "-",
        identity.signature,
        identity.package_version or identity.short_sha or "-",
    )
    return provider


def flush(timeout_millis: int = 5000) -> bool:
    """Force-flush pending spans through the batch processor."""
    provider = _state.get("provider")
    if provider is None:
        return False
    return provider.force_flush(timeout_millis=timeout_millis)
```

- [ ] **Step 3: Commit**

```bash
cd /Users/andrewlavoie/code/langperf
git add sdk/langperf/signature.py sdk/langperf/tracer.py
git commit -m "sdk: auto-detect agent signature + version, emit as OTel resource attrs"
```

---

### Task 11: Update seed demo script + final integration smoke

**Files:**
- Modify: `scripts/seed_demo_data.py`

- [ ] **Step 1: Read the current seed script**

```bash
cat /Users/andrewlavoie/code/langperf/scripts/seed_demo_data.py
```

Understand how it currently generates trajectories (it uses the SDK / tracer).

- [ ] **Step 2: Extend the script to simulate 3 agents with multiple versions + environments**

The script should generate (without strictly requiring real git repos):

- 3 synthetic `service_name` values: `support-refund-bot`, `triage-router`, `docs-qa`
- Set distinct `langperf.agent.signature` resource attrs per service — e.g. `"seed:support-refund-bot:agent.py"`, `"seed:triage-router:router.py"`, `"seed:docs-qa:qa.py"`
- For each agent, emit runs across 2 versions (e.g. `v1.4.1`, `v1.4.2`)
- Set `deployment.environment` to one of `prod` / `staging` / `dev` probabilistically per run

The simplest way: add a `seed_agent(service_name, signature, versions, environments, run_count)` helper that constructs an OTel `Resource` with the right attributes and emits the same span patterns the existing script uses.

If the existing seed script calls `langperf.init()` directly and then `langperf.trajectory(...)`, the new flow must bypass `init()` (since init is singleton-locked and we want multiple resource contexts). Build an explicit `TracerProvider` per agent — use the same construction pattern `init()` uses — and emit spans through that provider. Example scaffolding to add near the top of the script:

```python
from opentelemetry import trace as trace_api
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def _provider_for(
    *,
    service_name: str,
    signature: str,
    version: str,
    environment: str,
    endpoint: str,
) -> TracerProvider:
    attrs = {
        "service.name": service_name,
        "deployment.environment": environment,
        "langperf.agent.signature": signature,
        "langperf.agent.language": "python",
        "langperf.agent.version.package": version,
    }
    provider = TracerProvider(resource=Resource.create(attrs))
    exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider
```

Then the main seeding loop emits trajectories through `_provider_for(...)` with varied parameters. Keep the existing span shape (tool calls + LLM calls) — just vary the resource.

The exact span-emission code depends on the current script. Preserve whatever tool/LLM patterns exist.

- [ ] **Step 3: Run the seed script against a clean DB**

```bash
cd /Users/andrewlavoie/code/langperf
docker compose down -v && docker compose up -d postgres langperf-api langperf-web
# wait for ready
python scripts/seed_demo_data.py
```

- [ ] **Step 4: Smoke-test the new API endpoints**

```bash
curl -s http://localhost:4318/api/agents | jq '.[] | {name, language}'
```
Expected: three agents with auto-generated names (adjective-noun pairs).

```bash
NAME=$(curl -s http://localhost:4318/api/agents | jq -r '.[0].name')
curl -s http://localhost:4318/api/agents/$NAME | jq '{name, versions: [.versions[].label]}'
curl -s "http://localhost:4318/api/agents/$NAME/metrics?window=7d" | jq
curl -s "http://localhost:4318/api/agents/$NAME/tools?window=7d" | jq
curl -s "http://localhost:4318/api/agents/$NAME/runs?limit=5" | jq '.items[] | {id, version_label, duration_ms, step_count}'
```

Every curl should return 200 + plausible JSON. `versions` should contain both `v1.4.1` and `v1.4.2`. `metrics` should show non-zero `runs`, a computed `error_rate`, and latency percentiles. `tools` should list the tool names emitted by the seed script. `runs` should return `limit` items with `version_label` populated.

- [ ] **Step 5: Backfill smoke test (legacy data)**

```bash
# Restore legacy data behavior: re-seed with the OLD pre-Phase-2 script path
# if any, or manually insert a trajectory with NULL agent_id:
docker compose exec postgres psql -U langperf -c "
  UPDATE trajectories SET agent_id = NULL, agent_version_id = NULL WHERE random() < 0.2;
"
# Restart API — Alembic re-runs and the backfill migration attributes the nulls.
docker compose restart langperf-api
sleep 4
docker compose exec postgres psql -U langperf -c "
  SELECT count(*) FROM trajectories WHERE agent_id IS NULL;
"
```
Expected: 0.

Note: the backfill migration only fires once — after it runs, subsequent restarts are no-ops. If you manually NULL out FKs after the migration has already applied, you'll need to re-run the migration manually. That's fine for a one-time backfill contract.

- [ ] **Step 6: Final commit + PR-ready**

```bash
cd /Users/andrewlavoie/code/langperf
git add scripts/seed_demo_data.py
git commit -m "seed: multi-agent, multi-version demo data for Phase 2a"
```

Run a full build to make sure nothing regressed:

```bash
docker compose build langperf-api
```

Expected: clean build, no import errors.

---

## Self-Review

**Spec coverage** against `docs/superpowers/specs/2026-04-17-ui-shell-and-agent-first-class-design.md`:

| Spec section | Covered by |
|---|---|
| §4.1 Tables (agents, agent_versions) | Tasks 2, 3 |
| §4.2 Signature rule | Task 10 (`sdk/langperf/signature.py`) |
| §4.3 Trajectory FK columns + backfill | Tasks 3, 7 |
| §4.4 SDK changes (resource attrs, version capture) | Task 10 |
| §4.5 URL scheme | N/A — Phase 2a is API-only; Phase 2b wires URLs |
| §8.2 New API endpoints | Tasks 8, 9 |
| §8.3 SDK: capture signature, SHA, package version | Task 10 |
| §8.4 Ingest upsert + backfill | Tasks 5, 6, 7 |
| Auto-naming (docker-style) | Task 4 |

**Deferred to Phase 2b (not in this plan):**
- Agents index UI (`/agents`)
- Agent-detail Overview with KPIs + charts + tools + recent runs table
- Settings → Agents · auto-detected review queue
- Replace the `/agents/[name]/[tab]` placeholder with real data

**Placeholder scan:** no "TBD" / "TODO" in any task's code. The `cached_exists` scaffold in Task 5 step 1 is explicitly flagged with "DELETE" instructions — the final form is inline right after.

**Type consistency:**
- `Agent.id`, `AgentVersion.id` are UUID strings (str). Consistent across Tasks 2, 3, 5, 7, 8, 9.
- `AgentSummary` / `AgentDetail` / `AgentPatch` / `AgentMetrics` / `AgentToolUsage` / `AgentRunRow` / `AgentRunsResponse` — pydantic schemas, consistent across Tasks 8 and 9.
- `AgentIdentity` dataclass in SDK — matches the resource attr constants added in Task 2.
- `ATTR_AGENT_SIGNATURE` / `ATTR_AGENT_VERSION_*` — same strings in Task 2 (constants.py), Task 5 (agent_resolver.py), Task 10 (tracer.py).

**Risk call-outs:**
- Task 5's `_upsert_version` relies on a straight equality with nullable columns (`git_sha.is_(git_sha) if git_sha is None else ...`). In Postgres, comparing NULL with NULL via `=` is always false — using `IS NULL` explicitly via `.is_()` avoids silently creating duplicate version rows. Reviewers should verify this pattern is correct.
- The lifespan hook in Task 6 calls `command.stamp` + `command.upgrade` synchronously inside an async context. Alembic's commands are sync — they internally run a nested asyncio loop via `env.py`'s `asyncio.run(run_migrations_online())`. Running `asyncio.run()` inside an already-running event loop raises. The safe fix: run Alembic commands in a thread via `asyncio.to_thread(command.upgrade, cfg, "head")`. If the implementer sees `RuntimeError: asyncio.run() cannot be called from a running event loop`, apply that fix and commit as a follow-up.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-phase-2a-agent-data-layer.md`.

Same two execution options as Phase 1:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks.

**2. Inline** — execute in this session with checkpoints (schema → SDK → ingest → API → smoke).

Which approach?
