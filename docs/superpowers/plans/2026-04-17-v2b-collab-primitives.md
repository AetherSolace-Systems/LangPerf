# V2b — Collab Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the human-collaboration surface on top of v2a's auth foundation — comments/threads on any trajectory node, @-mentions with notifications, reviewer assignment on trajectories, auth-gated shared links, and a failure-mode taxonomy UI that augments v1's manual tags.

**Architecture:** All collab entities (`Comment`, `Notification`, `SharedLink`, `FailureMode`, `ReviewerAssignment`) live under `api/app/models.py` and are scoped by `org_id`. Routes live in a single new `api/app/api/collab.py` (manageable size) or split into `comments.py`, `notifications.py`, etc. (preferred for clarity). Frontend adds a node-side comments thread that opens inline on the trajectory detail view, a header bell/drawer for notifications, reviewer assignment chips on trajectory cards, a share-link modal, and a failure-mode dropdown in the existing tag surface.

**Tech Stack:** Same as v2a — FastAPI, async SQLAlchemy, Alembic, Next.js, Tailwind, Playwright. Uses v2a's `require_user()` dependency everywhere.

**Depends on:** v2a must be fully merged — User, Organization, Session models plus `org_id` FKs on domain tables must exist.

---

## File Structure

**Backend:**
- `api/app/models.py` — add `Comment`, `CommentMention`, `Notification`, `SharedLink`, `FailureMode`, `TrajectoryFailureMode`, `ReviewerAssignment` (or a simple `assigned_user_id` column on `Trajectory`)
- `api/alembic/versions/0010_collab_primitives.py` — migration for the new tables and columns
- `api/app/api/comments.py` — `POST /api/trajectories/{id}/nodes/{span_id}/comments`, list, edit, delete, resolve
- `api/app/api/notifications.py` — list + mark-read endpoints
- `api/app/api/reviewers.py` — assign / unassign trajectories
- `api/app/api/shared_links.py` — create / revoke / resolve shared links
- `api/app/api/failure_modes.py` — list taxonomy, attach/detach tags
- `api/app/services/mentions.py` — parse `@display_name` references, resolve to users, fan out notifications
- `api/app/main.py` — register new routers
- `api/tests/test_api_comments.py`, `test_api_notifications.py`, `test_api_reviewers.py`, `test_api_shared_links.py`, `test_api_failure_modes.py`, `test_mentions.py`

**Frontend:**
- `web/lib/collab.ts` — client helpers (comments, notifications, reviewers, shared links, failure modes)
- `web/components/collab/comment-thread.tsx` — thread for a single node
- `web/components/collab/comment-composer.tsx` — textarea + @-mention autocomplete
- `web/components/collab/notifications-drawer.tsx` — header bell + drawer
- `web/components/collab/reviewer-chip.tsx` — trajectory-card reviewer chip + picker
- `web/components/collab/share-link-modal.tsx` — copy-link UI
- `web/components/collab/failure-mode-picker.tsx` — taxonomy dropdown, multi-select
- `web/components/trajectory/right-panel.tsx` — integrate comment thread into the existing kind-aware right panel
- `web/app/shared/[token]/page.tsx` — read-only shared trajectory view
- `web/tests/collab.spec.ts` — Playwright flow

---

## Task 1: Comment + CommentMention models

**Files:**
- Modify: `api/app/models.py`
- Create: `api/tests/test_models_comment.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_models_comment.py`:

```python
from app.models import (
    Comment,
    CommentMention,
    Organization,
    Trajectory,
    User,
)


async def test_comment_on_trajectory_node(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    u = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    session.add(u)
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t)
    await session.flush()

    c = Comment(
        org_id=org.id,
        trajectory_id=t.id,
        span_id="span-1",
        author_id=u.id,
        body="first comment",
    )
    session.add(c)
    await session.commit()
    await session.refresh(c)
    assert c.id is not None
    assert c.resolved is False


async def test_mention_points_to_user(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    author = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    mentioned = User(org_id=org.id, email="c@d", password_hash="x", display_name="C")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([author, mentioned, t])
    await session.flush()
    c = Comment(org_id=org.id, trajectory_id=t.id, span_id="s", author_id=author.id, body="hi @C")
    session.add(c)
    await session.flush()
    m = CommentMention(comment_id=c.id, user_id=mentioned.id)
    session.add(m)
    await session.commit()
    assert m.comment_id == c.id
    assert m.user_id == mentioned.id
```

- [ ] **Step 2: Run to verify fail**

Run: `cd api && pytest tests/test_models_comment.py -v`
Expected: ImportError.

- [ ] **Step 3: Add models**

Modify `api/app/models.py`:

```python
class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trajectory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    span_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    parent_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class CommentMention(Base):
    __tablename__ = "comment_mentions"

    comment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
```

- [ ] **Step 4: Run test**

Run: `cd api && pytest tests/test_models_comment.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_comment.py
git commit -m "feat: comment + mention models"
```

---

## Task 2: Notification model

**Files:**
- Modify: `api/app/models.py`
- Create: `api/tests/test_models_notification.py`

- [ ] **Step 1: Write failing test**

Create `api/tests/test_models_notification.py`:

```python
from app.models import Notification, Organization, User


async def test_notification_for_user(session):
    org = Organization(name="default", slug="default")
    session.add(org)
    await session.flush()
    u = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
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
```

- [ ] **Step 2: Run test**

Run: `cd api && pytest tests/test_models_notification.py -v`
Expected: FAIL.

- [ ] **Step 3: Add model**

```python
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
```

- [ ] **Step 4: Run test**

Run: `cd api && pytest tests/test_models_notification.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_notification.py
git commit -m "feat: notification model"
```

---

## Task 3: SharedLink model

**Files:**
- Modify: `api/app/models.py`
- Create: `api/tests/test_models_shared_link.py`

- [ ] **Step 1: Write failing test**

```python
from datetime import datetime, timedelta, timezone

from app.models import Organization, SharedLink, Trajectory, User


async def test_shared_link_creation(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
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
```

- [ ] **Step 2: Run — fail.**

- [ ] **Step 3: Add model**

```python
class SharedLink(Base):
    __tablename__ = "shared_links"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trajectory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
```

- [ ] **Step 4: Run — pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_shared_link.py
git commit -m "feat: shared link model"
```

---

## Task 4: FailureMode taxonomy + TrajectoryFailureMode junction

**Files:**
- Modify: `api/app/models.py`
- Create: `api/tests/test_models_failure_mode.py`

- [ ] **Step 1: Write failing test**

```python
from app.models import FailureMode, Organization, Trajectory, TrajectoryFailureMode, User


async def test_failure_mode_attached_to_trajectory(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([u, t]); await session.flush()
    fm = FailureMode(org_id=org.id, slug="wrong_tool", label="Wrong tool", color="warn")
    session.add(fm); await session.flush()
    link = TrajectoryFailureMode(trajectory_id=t.id, failure_mode_id=fm.id, tagged_by=u.id)
    session.add(link)
    await session.commit()
    assert link.trajectory_id == t.id
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Add models + seed data**

```python
class FailureMode(Base):
    __tablename__ = "failure_modes"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="steel-mist")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_failure_modes_org_slug"),)


class TrajectoryFailureMode(Base):
    __tablename__ = "trajectory_failure_modes"

    trajectory_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("trajectories.id", ondelete="CASCADE"), primary_key=True
    )
    failure_mode_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("failure_modes.id", ondelete="CASCADE"), primary_key=True
    )
    tagged_by: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tagged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
```

Seed defaults in the v2b migration (see Task 6): `wrong_tool`, `bad_args`, `hallucination`, `loop`, `misunderstood_intent`.

- [ ] **Step 4: Pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_failure_mode.py
git commit -m "feat: failure-mode taxonomy models"
```

---

## Task 5: Reviewer assignment — assigned_user_id on Trajectory

**Files:**
- Modify: `api/app/models.py` (Trajectory)
- Create: `api/tests/test_models_reviewer.py`

Rationale: a single assigned reviewer per trajectory is enough for v2b; multi-reviewer support defers to later. A nullable `assigned_user_id` FK on `Trajectory` is the simplest shape.

- [ ] **Step 1: Write failing test**

```python
from app.models import Organization, Trajectory, User


async def test_trajectory_can_be_assigned(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    u = User(org_id=org.id, email="a@b", password_hash="x", display_name="A")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([u, t]); await session.flush()
    t.assigned_user_id = u.id
    await session.commit()
    await session.refresh(t)
    assert t.assigned_user_id == u.id
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Add column to Trajectory**

```python
assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(
    PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
)
```

- [ ] **Step 4: Pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/models.py api/tests/test_models_reviewer.py
git commit -m "feat: assigned_user_id on Trajectory"
```

---

## Task 6: Alembic migration 0010

**Files:**
- Create: `api/alembic/versions/0010_collab_primitives.py`

- [ ] **Step 1: Author migration**

Create `api/alembic/versions/0010_collab_primitives.py`:

```python
"""collab primitives

Revision ID: 0010_collab_primitives
Revises: 0009_auth_identity
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision = "0010_collab_primitives"
down_revision = "0009_auth_identity"
branch_labels = None
depends_on = None

DEFAULT_FAILURE_MODES = [
    ("wrong_tool", "Wrong tool", "warn"),
    ("bad_args", "Bad args", "warn"),
    ("hallucination", "Hallucination", "peach-neon"),
    ("loop", "Loop", "peach-neon"),
    ("misunderstood_intent", "Misunderstood intent", "steel-mist"),
]


def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trajectory_id", PgUUID(as_uuid=True), sa.ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("span_id", sa.String(255), nullable=True),
        sa.Column("author_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_comment_id", PgUUID(as_uuid=True), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_comments_trajectory_id", "comments", ["trajectory_id"])
    op.create_index("ix_comments_span_id", "comments", ["span_id"])

    op.create_table(
        "comment_mentions",
        sa.Column("comment_id", PgUUID(as_uuid=True), sa.ForeignKey("comments.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "notifications",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])

    op.create_table(
        "shared_links",
        sa.Column("token", sa.String(64), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trajectory_id", PgUUID(as_uuid=True), sa.ForeignKey("trajectories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "failure_modes",
        sa.Column("id", PgUUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", PgUUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("color", sa.String(32), nullable=False, server_default="steel-mist"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("org_id", "slug", name="uq_failure_modes_org_slug"),
    )

    op.create_table(
        "trajectory_failure_modes",
        sa.Column("trajectory_id", PgUUID(as_uuid=True), sa.ForeignKey("trajectories.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("failure_mode_id", PgUUID(as_uuid=True), sa.ForeignKey("failure_modes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tagged_by", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tagged_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.add_column(
        "trajectories",
        sa.Column("assigned_user_id", PgUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_trajectories_assigned_user_id", "trajectories", ["assigned_user_id"])

    conn = op.get_bind()
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).all()
    now = datetime.now(timezone.utc)
    for (org_id,) in orgs:
        for slug, label, color in DEFAULT_FAILURE_MODES:
            conn.execute(
                sa.text(
                    "INSERT INTO failure_modes (id, org_id, slug, label, color, created_at) "
                    "VALUES (:id, :org_id, :slug, :label, :color, :ts)"
                ).bindparams(id=str(uuid.uuid4()), org_id=str(org_id), slug=slug, label=label, color=color, ts=now)
            )


def downgrade() -> None:
    op.drop_index("ix_trajectories_assigned_user_id", table_name="trajectories")
    op.drop_column("trajectories", "assigned_user_id")
    op.drop_table("trajectory_failure_modes")
    op.drop_table("failure_modes")
    op.drop_table("shared_links")
    op.drop_table("notifications")
    op.drop_table("comment_mentions")
    op.drop_index("ix_comments_span_id", table_name="comments")
    op.drop_index("ix_comments_trajectory_id", table_name="comments")
    op.drop_table("comments")
```

- [ ] **Step 2: Apply migration to dev DB**

Run: `cd api && alembic upgrade head`
Expected: success. Check new tables + columns in `psql`.

- [ ] **Step 3: Commit**

```bash
git add api/alembic/versions/0010_collab_primitives.py
git commit -m "feat: alembic migration for collab primitives"
```

---

## Task 7: Mention parsing service

**Files:**
- Create: `api/app/services/__init__.py` (empty) — if not already present
- Create: `api/app/services/mentions.py`
- Create: `api/tests/test_mentions.py`

- [ ] **Step 1: Write failing test**

```python
from app.models import Organization, User
from app.services.mentions import resolve_mentions


async def test_resolve_mentions_matches_display_name_and_email(session):
    org = Organization(name="default", slug="default")
    session.add(org); await session.flush()
    andrew = User(org_id=org.id, email="andrew@example.com", password_hash="x", display_name="Andrew")
    bea = User(org_id=org.id, email="bea@example.com", password_hash="x", display_name="Bea")
    session.add_all([andrew, bea]); await session.commit()

    users = await resolve_mentions(session, org.id, "hey @Andrew and @bea@example.com")
    ids = {u.id for u in users}
    assert andrew.id in ids
    assert bea.id in ids
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

Create `api/app/services/mentions.py`:

```python
import re
import uuid
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User

MENTION_RE = re.compile(r"@([A-Za-z0-9_.+-]+(?:@[A-Za-z0-9.-]+)?)")


async def resolve_mentions(db: AsyncSession, org_id: uuid.UUID, body: str) -> list[User]:
    raw = MENTION_RE.findall(body)
    if not raw:
        return []
    tokens = [t.strip() for t in raw]
    query = select(User).where(
        User.org_id == org_id,
        or_(User.display_name.in_(tokens), User.email.in_(tokens)),
    )
    result = await db.execute(query)
    return list(result.scalars().all())


def dedupe(users: Iterable[User]) -> list[User]:
    seen: set[uuid.UUID] = set()
    out: list[User] = []
    for u in users:
        if u.id in seen:
            continue
        seen.add(u.id)
        out.append(u)
    return out
```

- [ ] **Step 4: Pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/services api/tests/test_mentions.py
git commit -m "feat: mention parsing"
```

---

## Task 8: Comment routes — create / list / update / resolve / delete

**Files:**
- Create: `api/app/api/comments.py`
- Modify: `api/app/main.py` (include router)
- Create: `api/tests/test_api_comments.py`

- [ ] **Step 1: Write failing tests**

Create `api/tests/test_api_comments.py`:

```python
async def _bootstrap(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    assert r.status_code == 201
    return r.json()["user"]


async def test_create_comment_on_span(client, session):
    await _bootstrap(client)
    # Seed a trajectory for this org.
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t)
    await session.commit()

    r = await client.post(
        f"/api/trajectories/{t.id}/nodes/span-1/comments",
        json={"body": "first comment"},
    )
    assert r.status_code == 201
    assert r.json()["body"] == "first comment"


async def test_list_comments_returns_thread(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t)
    await session.commit()

    await client.post(f"/api/trajectories/{t.id}/nodes/span-1/comments", json={"body": "one"})
    await client.post(f"/api/trajectories/{t.id}/nodes/span-1/comments", json={"body": "two"})
    r = await client.get(f"/api/trajectories/{t.id}/nodes/span-1/comments")
    assert r.status_code == 200
    bodies = [c["body"] for c in r.json()]
    assert bodies == ["one", "two"]


async def test_resolve_comment(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit()
    created = await client.post(f"/api/trajectories/{t.id}/nodes/span-1/comments", json={"body": "x"})
    cid = created.json()["id"]
    r = await client.post(f"/api/comments/{cid}/resolve")
    assert r.status_code == 200
    assert r.json()["resolved"] is True


async def test_mention_creates_notification(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    # Add a second user in the org so we can mention them.
    reviewer = User(org_id=org.id, email="r@r", password_hash="x", display_name="Reviewer")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([reviewer, t]); await session.commit()

    r = await client.post(
        f"/api/trajectories/{t.id}/nodes/span-1/comments",
        json={"body": "ping @Reviewer"},
    )
    assert r.status_code == 201
    # Notification should exist for reviewer.
    from app.models import Notification
    notifs = (await session.execute(select(Notification).where(Notification.user_id == reviewer.id))).scalars().all()
    assert len(notifs) == 1
    assert notifs[0].kind == "mention"
```

- [ ] **Step 2: Fail (routes don't exist).**

- [ ] **Step 3: Implement router**

Create `api/app/api/comments.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Comment, CommentMention, Notification, Trajectory, User
from app.services.mentions import dedupe, resolve_mentions

router = APIRouter(tags=["comments"])


class CreateCommentPayload(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    parent_comment_id: uuid.UUID | None = None


class CommentDto(BaseModel):
    id: str
    trajectory_id: str
    span_id: str | None
    author_id: str
    author_display_name: str
    parent_comment_id: str | None
    body: str
    resolved: bool
    created_at: datetime
    updated_at: datetime


async def _load_dto(db: AsyncSession, comment: Comment) -> CommentDto:
    author = await db.get(User, comment.author_id)
    return CommentDto(
        id=str(comment.id),
        trajectory_id=str(comment.trajectory_id),
        span_id=comment.span_id,
        author_id=str(comment.author_id),
        author_display_name=author.display_name if author else "unknown",
        parent_comment_id=str(comment.parent_comment_id) if comment.parent_comment_id else None,
        body=comment.body,
        resolved=comment.resolved,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


async def _assert_trajectory_in_org(db: AsyncSession, trajectory_id: uuid.UUID, org_id: uuid.UUID):
    t = await db.get(Trajectory, trajectory_id)
    if t is None or t.org_id != org_id:
        raise HTTPException(status_code=404, detail="trajectory not found")
    return t


@router.post("/api/trajectories/{trajectory_id}/nodes/{span_id}/comments", status_code=201)
async def create_on_span(
    trajectory_id: uuid.UUID,
    span_id: str,
    payload: CreateCommentPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory_in_org(session, trajectory_id, user.org_id)
    comment = Comment(
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        span_id=span_id,
        author_id=user.id,
        body=payload.body,
        parent_comment_id=payload.parent_comment_id,
    )
    session.add(comment)
    await session.flush()

    mentioned = dedupe(await resolve_mentions(session, user.org_id, payload.body))
    for m in mentioned:
        if m.id == user.id:
            continue
        session.add(CommentMention(comment_id=comment.id, user_id=m.id))
        session.add(
            Notification(
                org_id=user.org_id,
                user_id=m.id,
                kind="mention",
                payload={
                    "comment_id": str(comment.id),
                    "trajectory_id": str(trajectory_id),
                    "span_id": span_id,
                    "author_display_name": user.display_name,
                    "excerpt": payload.body[:200],
                },
            )
        )

    await session.commit()
    await session.refresh(comment)
    return (await _load_dto(session, comment)).model_dump(mode="json")


@router.get("/api/trajectories/{trajectory_id}/nodes/{span_id}/comments")
async def list_on_span(
    trajectory_id: uuid.UUID,
    span_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory_in_org(session, trajectory_id, user.org_id)
    result = await session.execute(
        select(Comment)
        .where(Comment.trajectory_id == trajectory_id, Comment.span_id == span_id)
        .order_by(Comment.created_at.asc())
    )
    comments = list(result.scalars().all())
    return [(await _load_dto(session, c)).model_dump(mode="json") for c in comments]


@router.get("/api/trajectories/{trajectory_id}/comments")
async def list_on_trajectory(
    trajectory_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await _assert_trajectory_in_org(session, trajectory_id, user.org_id)
    result = await session.execute(
        select(Comment)
        .where(Comment.trajectory_id == trajectory_id)
        .order_by(Comment.created_at.asc())
    )
    comments = list(result.scalars().all())
    return [(await _load_dto(session, c)).model_dump(mode="json") for c in comments]


@router.patch("/api/comments/{comment_id}")
async def update(
    comment_id: uuid.UUID,
    payload: CreateCommentPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if comment.author_id != user.id:
        raise HTTPException(status_code=403, detail="not the author")
    comment.body = payload.body
    await session.commit()
    await session.refresh(comment)
    return (await _load_dto(session, comment)).model_dump(mode="json")


@router.post("/api/comments/{comment_id}/resolve")
async def resolve(
    comment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    comment.resolved = True
    await session.commit()
    await session.refresh(comment)
    return (await _load_dto(session, comment)).model_dump(mode="json")


@router.delete("/api/comments/{comment_id}", status_code=204)
async def delete(
    comment_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    comment = await session.get(Comment, comment_id)
    if comment is None or comment.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    if comment.author_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="not allowed")
    await session.delete(comment)
    await session.commit()
```

- [ ] **Step 4: Register router**

Modify `api/app/main.py`:

```python
from app.api import comments as comments_api
...
app.include_router(comments_api.router)
```

- [ ] **Step 5: Run tests**

Run: `cd api && pytest tests/test_api_comments.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/api/comments.py api/app/main.py api/tests/test_api_comments.py
git commit -m "feat: comment endpoints + @-mention notifications"
```

---

## Task 9: Notifications endpoints

**Files:**
- Create: `api/app/api/notifications.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_api_notifications.py`

- [ ] **Step 1: Write failing tests**

```python
async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )


async def test_list_notifications_empty(client):
    await _bootstrap(client)
    r = await client.get("/api/notifications")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_notifications_after_mention(client, session):
    await _bootstrap(client)
    from app.models import Notification, Organization, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    me = (await session.execute(select(User).where(User.email == "a@b"))).scalar_one()
    session.add(Notification(org_id=org.id, user_id=me.id, kind="mention", payload={"x": 1}))
    await session.commit()
    r = await client.get("/api/notifications")
    body = r.json()
    assert len(body) == 1
    assert body[0]["kind"] == "mention"


async def test_mark_read(client, session):
    await _bootstrap(client)
    from app.models import Notification, Organization, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    me = (await session.execute(select(User).where(User.email == "a@b"))).scalar_one()
    n = Notification(org_id=org.id, user_id=me.id, kind="mention", payload={"x": 1})
    session.add(n); await session.commit(); await session.refresh(n)
    r = await client.post(f"/api/notifications/{n.id}/read")
    assert r.status_code == 204
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/api/notifications.py
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Notification

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
    unread_only: bool = False,
    limit: int = 50,
):
    q = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [
        {
            "id": str(n.id),
            "kind": n.kind,
            "payload": n.payload,
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "created_at": n.created_at.isoformat(),
        }
        for n in rows
    ]


@router.post("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    n = await session.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="not found")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        await session.commit()
    return Response(status_code=204)


@router.post("/read-all", status_code=204)
async def mark_all_read(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await session.commit()
    return Response(status_code=204)
```

Register in `main.py`:

```python
from app.api import notifications as notifications_api
app.include_router(notifications_api.router)
```

- [ ] **Step 4: Pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/api/notifications.py api/app/main.py api/tests/test_api_notifications.py
git commit -m "feat: notifications list + mark-read"
```

---

## Task 10: Reviewer assignment endpoints

**Files:**
- Create: `api/app/api/reviewers.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_api_reviewers.py`

- [ ] **Step 1: Write failing tests**

```python
async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )


async def test_assign_reviewer_creates_notification(client, session):
    await _bootstrap(client)
    from app.models import Notification, Organization, Trajectory, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    me = (await session.execute(select(User).where(User.email == "a@b"))).scalar_one()
    reviewer = User(org_id=org.id, email="r@r", password_hash="x", display_name="R")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add_all([reviewer, t]); await session.commit()

    r = await client.post(
        f"/api/trajectories/{t.id}/assign",
        json={"user_id": str(reviewer.id)},
    )
    assert r.status_code == 200
    assert r.json()["assigned_user_id"] == str(reviewer.id)

    notifs = (await session.execute(select(Notification).where(Notification.user_id == reviewer.id))).scalars().all()
    assert any(n.kind == "assigned" for n in notifs)


async def test_unassign_reviewer(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory, User
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    reviewer = User(org_id=org.id, email="r@r", password_hash="x", display_name="R")
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n", assigned_user_id=None)
    session.add_all([reviewer, t]); await session.commit()
    await client.post(f"/api/trajectories/{t.id}/assign", json={"user_id": str(reviewer.id)})
    r = await client.post(f"/api/trajectories/{t.id}/assign", json={"user_id": None})
    assert r.status_code == 200
    assert r.json()["assigned_user_id"] is None
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/api/reviewers.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import Notification, Trajectory, User

router = APIRouter(tags=["reviewers"])


class AssignPayload(BaseModel):
    user_id: uuid.UUID | None


@router.post("/api/trajectories/{trajectory_id}/assign")
async def assign(
    trajectory_id: uuid.UUID,
    payload: AssignPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")

    if payload.user_id is not None:
        assignee = await session.get(User, payload.user_id)
        if assignee is None or assignee.org_id != user.org_id:
            raise HTTPException(status_code=400, detail="invalid assignee")
        t.assigned_user_id = assignee.id
        session.add(
            Notification(
                org_id=user.org_id,
                user_id=assignee.id,
                kind="assigned",
                payload={
                    "trajectory_id": str(trajectory_id),
                    "assigned_by": user.display_name,
                },
            )
        )
    else:
        t.assigned_user_id = None

    await session.commit()
    await session.refresh(t)
    return {
        "trajectory_id": str(t.id),
        "assigned_user_id": str(t.assigned_user_id) if t.assigned_user_id else None,
    }
```

Register in `main.py`.

- [ ] **Step 4: Pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/api/reviewers.py api/app/main.py api/tests/test_api_reviewers.py
git commit -m "feat: reviewer assignment + notification"
```

---

## Task 11: Shared link endpoints

**Files:**
- Create: `api/app/api/shared_links.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_api_shared_links.py`

- [ ] **Step 1: Write failing tests**

```python
async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )


async def test_create_shared_link(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit()
    r = await client.post(f"/api/trajectories/{t.id}/share", json={})
    assert r.status_code == 201
    assert r.json()["token"]


async def test_resolve_shared_link_for_authed_user_same_org(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit()
    created = await client.post(f"/api/trajectories/{t.id}/share", json={})
    token = created.json()["token"]
    r = await client.get(f"/api/shared/{token}")
    assert r.status_code == 200
    assert r.json()["trajectory_id"] == str(t.id)


async def test_resolve_revoked_link_is_404(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit()
    created = await client.post(f"/api/trajectories/{t.id}/share", json={})
    token = created.json()["token"]
    await client.post(f"/api/shared/{token}/revoke")
    r = await client.get(f"/api/shared/{token}")
    assert r.status_code == 404
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/api/shared_links.py
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import SharedLink, Trajectory

router = APIRouter(tags=["shared_links"])


class CreateSharePayload(BaseModel):
    expires_in_days: int | None = 30


@router.post("/api/trajectories/{trajectory_id}/share", status_code=201)
async def create_share(
    trajectory_id: uuid.UUID,
    payload: CreateSharePayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    link = SharedLink(
        token=secrets.token_urlsafe(32),
        org_id=user.org_id,
        trajectory_id=trajectory_id,
        created_by=user.id,
        expires_at=(datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days))
        if payload.expires_in_days
        else None,
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return {"token": link.token, "trajectory_id": str(trajectory_id), "expires_at": link.expires_at.isoformat() if link.expires_at else None}


@router.post("/api/shared/{token}/revoke")
async def revoke(
    token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    link = await session.get(SharedLink, token)
    if link is None or link.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    link.revoked = True
    await session.commit()
    return {"token": token, "revoked": True}


@router.get("/api/shared/{token}")
async def resolve(
    token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    link = await session.get(SharedLink, token)
    if link is None or link.revoked:
        raise HTTPException(status_code=404, detail="not found")
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="not found")
    if link.org_id != user.org_id:
        raise HTTPException(status_code=403, detail="cross-org sharing not supported in v2")
    return {"token": token, "trajectory_id": str(link.trajectory_id), "org_id": str(link.org_id)}
```

Register in `main.py`.

- [ ] **Step 4: Pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/api/shared_links.py api/app/main.py api/tests/test_api_shared_links.py
git commit -m "feat: shared links create/revoke/resolve"
```

---

## Task 12: Failure-mode tagging endpoints

**Files:**
- Create: `api/app/api/failure_modes.py`
- Modify: `api/app/main.py`
- Create: `api/tests/test_api_failure_modes.py`

- [ ] **Step 1: Write failing tests**

```python
async def _bootstrap(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )


async def test_list_failure_modes_seeded(client):
    await _bootstrap(client)
    r = await client.get("/api/failure-modes")
    assert r.status_code == 200
    slugs = [m["slug"] for m in r.json()]
    assert "wrong_tool" in slugs
    assert "hallucination" in slugs


async def test_tag_and_untag_trajectory(client, session):
    await _bootstrap(client)
    from app.models import Organization, Trajectory
    from sqlalchemy import select
    org = (await session.execute(select(Organization))).scalar_one()
    t = Trajectory(org_id=org.id, trace_id="t", service_name="svc", name="n")
    session.add(t); await session.commit()

    modes = (await client.get("/api/failure-modes")).json()
    loop = next(m for m in modes if m["slug"] == "loop")
    r = await client.post(f"/api/trajectories/{t.id}/failure-modes", json={"failure_mode_id": loop["id"]})
    assert r.status_code == 200
    tagged = (await client.get(f"/api/trajectories/{t.id}/failure-modes")).json()
    assert any(m["slug"] == "loop" for m in tagged)
    r2 = await client.delete(f"/api/trajectories/{t.id}/failure-modes/{loop['id']}")
    assert r2.status_code == 204
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
# api/app/api/failure_modes.py
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import FailureMode, Trajectory, TrajectoryFailureMode

router = APIRouter(tags=["failure_modes"])


class TagPayload(BaseModel):
    failure_mode_id: uuid.UUID


def _dto(m: FailureMode) -> dict:
    return {"id": str(m.id), "slug": m.slug, "label": m.label, "color": m.color}


@router.get("/api/failure-modes")
async def list_modes(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    rows = (await session.execute(
        select(FailureMode).where(FailureMode.org_id == user.org_id).order_by(FailureMode.label)
    )).scalars().all()
    return [_dto(m) for m in rows]


@router.post("/api/trajectories/{trajectory_id}/failure-modes")
async def tag(
    trajectory_id: uuid.UUID,
    payload: TagPayload,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    mode = await session.get(FailureMode, payload.failure_mode_id)
    if mode is None or mode.org_id != user.org_id:
        raise HTTPException(status_code=400, detail="invalid failure mode")
    existing = await session.get(TrajectoryFailureMode, (trajectory_id, payload.failure_mode_id))
    if existing is None:
        session.add(TrajectoryFailureMode(trajectory_id=trajectory_id, failure_mode_id=payload.failure_mode_id, tagged_by=user.id))
        await session.commit()
    return {"trajectory_id": str(trajectory_id), "failure_mode_id": str(payload.failure_mode_id)}


@router.get("/api/trajectories/{trajectory_id}/failure-modes")
async def list_tagged(
    trajectory_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    rows = (await session.execute(
        select(FailureMode).join(
            TrajectoryFailureMode, TrajectoryFailureMode.failure_mode_id == FailureMode.id
        ).where(TrajectoryFailureMode.trajectory_id == trajectory_id)
    )).scalars().all()
    return [_dto(m) for m in rows]


@router.delete("/api/trajectories/{trajectory_id}/failure-modes/{failure_mode_id}", status_code=204)
async def untag(
    trajectory_id: uuid.UUID,
    failure_mode_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    t = await session.get(Trajectory, trajectory_id)
    if t is None or t.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="not found")
    link = await session.get(TrajectoryFailureMode, (trajectory_id, failure_mode_id))
    if link:
        await session.delete(link)
        await session.commit()
    return Response(status_code=204)
```

Register in `main.py`.

- [ ] **Step 4: Pass.**

- [ ] **Step 5: Commit**

```bash
git add api/app/api/failure_modes.py api/app/main.py api/tests/test_api_failure_modes.py
git commit -m "feat: failure-mode taxonomy + tagging endpoints"
```

---

## Task 13: Frontend — collab client helpers

**Files:**
- Create: `web/lib/collab.ts`

- [ ] **Step 1: Implement**

Create `web/lib/collab.ts`:

```ts
import { CLIENT_API_URL, SERVER_API_URL } from "./api";

export type Comment = {
  id: string;
  trajectory_id: string;
  span_id: string | null;
  author_id: string;
  author_display_name: string;
  parent_comment_id: string | null;
  body: string;
  resolved: boolean;
  created_at: string;
  updated_at: string;
};

export type Notification = {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
};

export type FailureMode = {
  id: string;
  slug: string;
  label: string;
  color: string;
};

export async function listComments(trajectoryId: string, spanId: string, cookie?: string): Promise<Comment[]> {
  const res = await fetch(
    `${SERVER_API_URL}/api/trajectories/${trajectoryId}/nodes/${spanId}/comments`,
    { headers: cookie ? { cookie } : {}, cache: "no-store" },
  );
  if (!res.ok) throw new Error(`listComments ${res.status}`);
  return res.json();
}

export async function createComment(trajectoryId: string, spanId: string, body: string): Promise<Comment> {
  const res = await fetch(
    `${CLIENT_API_URL}/api/trajectories/${trajectoryId}/nodes/${spanId}/comments`,
    {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ body }),
    },
  );
  if (!res.ok) throw new Error(`createComment ${res.status}`);
  return res.json();
}

export async function resolveComment(commentId: string): Promise<Comment> {
  const res = await fetch(`${CLIENT_API_URL}/api/comments/${commentId}/resolve`, {
    method: "POST",
    credentials: "include",
  });
  return res.json();
}

export async function listNotifications(unreadOnly = false, cookie?: string): Promise<Notification[]> {
  const url = `${SERVER_API_URL}/api/notifications${unreadOnly ? "?unread_only=true" : ""}`;
  const res = await fetch(url, { headers: cookie ? { cookie } : {}, cache: "no-store" });
  return res.json();
}

export async function markNotificationRead(id: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/notifications/${id}/read`, {
    method: "POST",
    credentials: "include",
  });
}

export async function listFailureModes(cookie?: string): Promise<FailureMode[]> {
  const res = await fetch(`${SERVER_API_URL}/api/failure-modes`, {
    headers: cookie ? { cookie } : {}, cache: "no-store",
  });
  return res.json();
}

export async function tagFailureMode(trajectoryId: string, failureModeId: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/failure-modes`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ failure_mode_id: failureModeId }),
  });
}

export async function untagFailureMode(trajectoryId: string, failureModeId: string): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/failure-modes/${failureModeId}`, {
    method: "DELETE",
    credentials: "include",
  });
}

export async function assignReviewer(trajectoryId: string, userId: string | null): Promise<void> {
  await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/assign`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
}

export async function createShareLink(trajectoryId: string): Promise<{ token: string }> {
  const res = await fetch(`${CLIENT_API_URL}/api/trajectories/${trajectoryId}/share`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({}),
  });
  return res.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add web/lib/collab.ts
git commit -m "feat: collab client helpers"
```

---

## Task 14: Comment thread component

**Files:**
- Create: `web/components/collab/comment-thread.tsx`
- Create: `web/components/collab/comment-composer.tsx`

- [ ] **Step 1: Thread**

Create `web/components/collab/comment-thread.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

import { type Comment, createComment, listComments, resolveComment } from "@/lib/collab";
import { CommentComposer } from "./comment-composer";

export function CommentThread({
  trajectoryId,
  spanId,
}: {
  trajectoryId: string;
  spanId: string;
}) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    listComments(trajectoryId, spanId).then((res) => {
      if (!cancelled) { setComments(res); setLoading(false); }
    });
    return () => { cancelled = true; };
  }, [trajectoryId, spanId]);

  async function onSubmit(body: string) {
    const created = await createComment(trajectoryId, spanId, body);
    setComments((prev) => [...prev, created]);
  }

  async function onResolve(id: string) {
    const updated = await resolveComment(id);
    setComments((prev) => prev.map((c) => (c.id === id ? updated : c)));
  }

  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-warm-fog/70">
        Comments
      </h3>
      {loading && <p className="text-xs text-warm-fog/50">Loading…</p>}
      <ul className="flex flex-col gap-2">
        {comments.map((c) => (
          <li
            key={c.id}
            className={`rounded-lg bg-warm-fog/5 p-3 text-sm ring-1 ring-warm-fog/10 ${
              c.resolved ? "opacity-50" : ""
            }`}
          >
            <div className="flex items-center justify-between text-xs text-warm-fog/60">
              <span className="font-medium text-aether-teal">{c.author_display_name}</span>
              <div className="flex items-center gap-2">
                <span>{new Date(c.created_at).toLocaleString()}</span>
                {!c.resolved && (
                  <button className="text-xs text-peach-neon" onClick={() => onResolve(c.id)}>
                    resolve
                  </button>
                )}
              </div>
            </div>
            <p className="mt-1 whitespace-pre-wrap text-warm-fog">{c.body}</p>
          </li>
        ))}
      </ul>
      <CommentComposer onSubmit={onSubmit} />
    </div>
  );
}
```

- [ ] **Step 2: Composer**

Create `web/components/collab/comment-composer.tsx`:

```tsx
"use client";

import { useState } from "react";

export function CommentComposer({ onSubmit }: { onSubmit: (body: string) => Promise<void> }) {
  const [body, setBody] = useState("");
  const [pending, setPending] = useState(false);

  async function submit() {
    if (!body.trim()) return;
    setPending(true);
    try {
      await onSubmit(body);
      setBody("");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Leave a comment. @mention to notify a teammate."
        rows={3}
        className="w-full resize-none rounded-lg bg-carbon p-3 text-sm text-warm-fog ring-1 ring-warm-fog/10 focus:outline-none focus:ring-aether-teal"
      />
      <button
        onClick={submit}
        disabled={pending || !body.trim()}
        className="self-end rounded bg-aether-teal px-3 py-1 text-xs font-semibold text-carbon disabled:opacity-50"
      >
        {pending ? "Posting…" : "Post"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Wire into existing right-panel**

Modify the existing kind-aware right panel component (discover via `grep -rn "right-panel\|RightPanel" web/components`) to render `<CommentThread trajectoryId={...} spanId={selected.spanId} />` when a span is selected.

- [ ] **Step 4: Commit**

```bash
git add web/components/collab web/components
git commit -m "feat: node comment thread UI"
```

---

## Task 15: Notifications drawer in top bar

**Files:**
- Create: `web/components/collab/notifications-drawer.tsx`
- Modify: top-bar component

- [ ] **Step 1: Drawer**

Create `web/components/collab/notifications-drawer.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

import { listNotifications, markNotificationRead, type Notification } from "@/lib/collab";

export function NotificationsDrawer() {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Notification[]>([]);

  useEffect(() => {
    if (!open) return;
    listNotifications(false).then(setItems);
  }, [open]);

  async function onClick(n: Notification) {
    if (!n.read_at) await markNotificationRead(n.id);
    setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x)));
  }

  const unreadCount = items.filter((i) => !i.read_at).length;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((x) => !x)}
        className="relative rounded-full p-2 text-warm-fog hover:bg-warm-fog/10"
        aria-label="Notifications"
      >
        🔔
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-warn px-1 text-[0.65rem] text-carbon">
            {unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-lg bg-warm-fog/5 shadow-xl ring-1 ring-warm-fog/10">
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <p className="p-4 text-sm text-warm-fog/60">No notifications</p>
            ) : (
              <ul>
                {items.map((n) => (
                  <li
                    key={n.id}
                    onClick={() => onClick(n)}
                    className={`cursor-pointer border-b border-warm-fog/10 p-3 text-sm ${
                      n.read_at ? "opacity-60" : ""
                    }`}
                  >
                    <p className="text-warm-fog">
                      <span className="text-aether-teal">{n.kind}</span>{" "}
                      — {JSON.stringify(n.payload).slice(0, 120)}
                    </p>
                    <p className="text-xs text-warm-fog/40">{new Date(n.created_at).toLocaleString()}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Mount in top bar**

Modify the existing top-bar component — render `<NotificationsDrawer />` before `<UserMenu />`.

- [ ] **Step 3: Commit**

```bash
git add web/components/collab/notifications-drawer.tsx web/components
git commit -m "feat: notifications drawer in top bar"
```

---

## Task 16: Reviewer chip + picker on trajectory cards

**Files:**
- Create: `web/components/collab/reviewer-chip.tsx`
- Modify: trajectory card component (discover via `grep -rn "TrajectoryCard\|trajectory-card" web/components`)

- [ ] **Step 1: Component**

Create `web/components/collab/reviewer-chip.tsx`:

```tsx
"use client";

import { useState } from "react";

import { assignReviewer } from "@/lib/collab";

type Member = { id: string; display_name: string };

export function ReviewerChip({
  trajectoryId,
  current,
  members,
}: {
  trajectoryId: string;
  current: Member | null;
  members: Member[];
}) {
  const [open, setOpen] = useState(false);
  const [assigned, setAssigned] = useState<Member | null>(current);

  async function pick(m: Member | null) {
    setAssigned(m);
    await assignReviewer(trajectoryId, m?.id ?? null);
    setOpen(false);
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((x) => !x)}
        className="rounded-full bg-warm-fog/10 px-2 py-1 text-xs text-warm-fog hover:bg-warm-fog/20"
      >
        {assigned ? `@${assigned.display_name}` : "Assign"}
      </button>
      {open && (
        <div className="absolute z-40 mt-1 w-44 rounded-lg bg-carbon p-1 ring-1 ring-warm-fog/20">
          <button onClick={() => pick(null)} className="block w-full px-2 py-1 text-left text-xs hover:bg-warm-fog/10">
            Unassign
          </button>
          {members.map((m) => (
            <button
              key={m.id}
              onClick={() => pick(m)}
              className="block w-full px-2 py-1 text-left text-xs text-warm-fog hover:bg-warm-fog/10"
            >
              {m.display_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add backend `/api/org/members` endpoint**

Create a small route in `api/app/api/auth.py` (it already exists) or a new file:

```python
@router.get("/org/members")
async def list_members(
    session: Annotated[AsyncSession, Depends(get_session)],
    user=require_user(),
):
    from sqlalchemy import select
    from app.models import User as UserModel
    rows = (await session.execute(
        select(UserModel).where(UserModel.org_id == user.org_id).order_by(UserModel.display_name)
    )).scalars().all()
    return [{"id": str(u.id), "display_name": u.display_name} for u in rows]
```

Add a corresponding `listMembers()` helper in `web/lib/auth.ts`.

- [ ] **Step 3: Wire into trajectory card**

Modify the trajectory card component to accept `assigned` + `members` props and render `<ReviewerChip />`.

- [ ] **Step 4: Commit**

```bash
git add api/app/api/auth.py web/components/collab/reviewer-chip.tsx web/lib/auth.ts web/components
git commit -m "feat: reviewer chip + org members endpoint"
```

---

## Task 17: Failure-mode picker

**Files:**
- Create: `web/components/collab/failure-mode-picker.tsx`
- Modify: trajectory detail header (or existing tag surface) to render picker

- [ ] **Step 1: Picker**

Create `web/components/collab/failure-mode-picker.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";

import { type FailureMode, listFailureModes, tagFailureMode, untagFailureMode } from "@/lib/collab";

export function FailureModePicker({ trajectoryId, current }: { trajectoryId: string; current: FailureMode[] }) {
  const [all, setAll] = useState<FailureMode[]>([]);
  const [tagged, setTagged] = useState<FailureMode[]>(current);

  useEffect(() => {
    listFailureModes().then(setAll);
  }, []);

  async function toggle(m: FailureMode) {
    const isTagged = tagged.some((t) => t.id === m.id);
    if (isTagged) {
      await untagFailureMode(trajectoryId, m.id);
      setTagged((prev) => prev.filter((t) => t.id !== m.id));
    } else {
      await tagFailureMode(trajectoryId, m.id);
      setTagged((prev) => [...prev, m]);
    }
  }

  return (
    <div className="flex flex-wrap gap-1">
      {all.map((m) => {
        const active = tagged.some((t) => t.id === m.id);
        return (
          <button
            key={m.id}
            onClick={() => toggle(m)}
            className={`rounded-full px-2 py-0.5 text-xs ring-1 ${
              active
                ? "bg-warn/20 text-warn ring-warn"
                : "bg-warm-fog/5 text-warm-fog/70 ring-warm-fog/20"
            }`}
          >
            {m.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Mount in trajectory detail**

Modify `web/app/t/[id]/page.tsx` or `web/app/r/[run_id]/page.tsx` header to pre-fetch tagged failure modes server-side and render the picker.

- [ ] **Step 3: Commit**

```bash
git add web/components/collab/failure-mode-picker.tsx web/app
git commit -m "feat: failure-mode picker UI"
```

---

## Task 18: Shared link modal + /shared/[token] page

**Files:**
- Create: `web/components/collab/share-link-modal.tsx`
- Create: `web/app/shared/[token]/page.tsx`

- [ ] **Step 1: Modal**

Create `web/components/collab/share-link-modal.tsx`:

```tsx
"use client";

import { useState } from "react";

import { createShareLink } from "@/lib/collab";

export function ShareLinkModal({ trajectoryId }: { trajectoryId: string }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState<string | null>(null);

  async function generate() {
    const { token } = await createShareLink(trajectoryId);
    const origin = typeof window !== "undefined" ? window.location.origin : "";
    setUrl(`${origin}/shared/${token}`);
  }

  return (
    <>
      <button
        onClick={() => { setOpen(true); if (!url) generate(); }}
        className="rounded bg-warm-fog/10 px-2 py-1 text-xs text-warm-fog hover:bg-warm-fog/20"
      >
        Share
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setOpen(false)}>
          <div className="w-96 rounded-lg bg-warm-fog/10 p-4 ring-1 ring-warm-fog/20" onClick={(e) => e.stopPropagation()}>
            <h3 className="mb-2 text-sm font-semibold text-aether-teal">Share this trajectory</h3>
            {url ? (
              <div className="space-y-2">
                <input
                  readOnly
                  value={url}
                  className="w-full rounded bg-carbon px-3 py-2 text-xs text-warm-fog"
                />
                <p className="text-[0.65rem] text-warm-fog/50">Anyone signed into your org can open this link.</p>
              </div>
            ) : (
              <p className="text-xs text-warm-fog/60">Generating link…</p>
            )}
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Shared page**

Create `web/app/shared/[token]/page.tsx`:

```tsx
import { headers } from "next/headers";
import { notFound, redirect } from "next/navigation";

import { SERVER_API_URL } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function SharedPage({ params }: { params: { token: string } }) {
  const cookie = headers().get("cookie") ?? "";
  const res = await fetch(`${SERVER_API_URL}/api/shared/${params.token}`, {
    headers: { cookie },
    cache: "no-store",
  });
  if (res.status === 404) notFound();
  if (res.status === 401) redirect(`/login?next=/shared/${params.token}`);
  const body = await res.json();
  redirect(`/t/${body.trajectory_id}`);
}
```

- [ ] **Step 3: Commit**

```bash
git add web/components/collab/share-link-modal.tsx web/app/shared
git commit -m "feat: share-link modal + shared route"
```

---

## Task 19: Playwright — full collab flow

**Files:**
- Create: `web/tests/collab.spec.ts`

- [ ] **Step 1: Write the spec**

```ts
import { expect, test } from "@playwright/test";

test("comment and resolve on a span", async ({ page }) => {
  // Assumes auth has been bootstrapped once earlier and trajectory data was seeded.
  await page.goto("/");
  await page.getByRole("link", { name: /history|trajectories/i }).first().click();
  await page.locator("[data-testid^='trajectory-row-']").first().click();
  await page.locator("[data-testid^='tree-node-']").first().click();

  const body = `auto-test-${Date.now()}`;
  await page.getByPlaceholder(/leave a comment/i).fill(body);
  await page.getByRole("button", { name: /^Post$/ }).click();
  await expect(page.getByText(body)).toBeVisible();
  await page.getByText("resolve").first().click();
});
```

- [ ] **Step 2: Run**

Run: `cd web && npm test -- collab.spec.ts`
Expected: PASS (requires seeded data). Document in `README.md` the seed command.

- [ ] **Step 3: Commit**

```bash
git add web/tests/collab.spec.ts
git commit -m "tests: playwright collab flow"
```

---

## Notes for the implementer

- **Mention resolution** is display-name- or email-based. Display names inside an org are not unique by constraint — dedupe when resolving.
- **Email notifications** are NOT in this plan (deferred); in-app notifications via `/api/notifications` are the only channel.
- **Testing seeded data**: the Playwright spec assumes there's at least one trajectory in the dev DB. Add a test fixture to seed one if the repo doesn't already have a dev-seed helper.
- **Cookies across origins**: the frontend runs on `:3030` and API on `:4318`. Ensure the API sets `Access-Control-Allow-Credentials: true` and the frontend fetch uses `credentials: "include"`. The existing CORS config (`allow_origins=["*"]`) must be narrowed to `["http://localhost:3030"]` when credentials are enabled — update in v2a or v2b as a prerequisite.
- **Commit style**: `feat:`, `tests:`, `docs:`, `chore:` match repo conventions.
