# Agent-Centric Improvement Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the agent detail page into the surface where engineers see what's broken (ranked worklist + 4-chart trend grid with shared hover-cursor) and walk away with exportable artifacts (`profile.md` + `failures.csv`). Adds end-user thumbs-down SDK capture and auto-stamps trajectory completion.

**Architecture:** One append-only Alembic migration adds 3 columns to `trajectories`. SDK gains `langperf.feedback()` + auto-stamps `langperf.completed` on trajectory `__exit__`. Backend adds 1 ingest route (`POST /v1/feedback`) and 4 agent-scoped read routes (worklist, timeseries, profile.md, failures.csv), each backed by a dedicated service module. Web adds 4 components (`SharedCursorProvider`, `TrendChart`, `AgentWorklist`, `ExportBar`) and rewires the Overview tab to use them.

**Tech Stack:** Python 3.12, FastAPI, async SQLAlchemy 2.0, Alembic; pytest (sqlite + postgres service-container lanes); Next.js 14 App Router, TypeScript, Tailwind; vitest + Playwright.

**Spec:** `docs/superpowers/specs/2026-04-22-agent-centric-improvement-loop-design.md`.

---

## File structure

### New files (22)

```
api/alembic/versions/0017_feedback_and_completion.py
api/app/api/feedback.py
api/app/services/agent_worklist.py
api/app/services/agent_timeseries.py
api/app/services/agent_profile.py
api/app/services/agent_failures.py
api/tests/test_api_feedback.py
api/tests/test_completed_ingest.py
api/tests/test_worklist_scoring.py
api/tests/test_worklist_e2e.py
api/tests/test_agent_timeseries.py
api/tests/test_agent_profile_render.py
api/tests/test_agent_failures_csv.py
sdk/langperf/feedback.py
sdk/tests/test_feedback.py
sdk/tests/test_trajectory_completed.py
web/components/charts/shared-cursor.tsx
web/components/charts/trend-chart.tsx
web/components/agent/worklist.tsx
web/components/agent/export-bar.tsx
web/tests/unit/shared-cursor.test.tsx
web/tests/unit/trend-chart.test.tsx
```

### Modified files (11)

```
api/app/models.py                      # Trajectory: feedback_thumbs_down, feedback_thumbs_up, completed
api/app/constants.py                   # ATTR_COMPLETED = "langperf.completed"
api/app/otlp/ingest.py                 # _apply_sdk_signals reads completed
api/app/api/agents.py                  # 4 new agent-scoped routes
api/app/main.py                        # register feedback router
sdk/langperf/__init__.py               # export feedback + __version__ bump to 0.3.0
sdk/langperf/attributes.py             # COMPLETED = "langperf.completed"
sdk/langperf/trajectory.py             # __exit__ stamps completed attribute
sdk/pyproject.toml                     # version = "0.3.0"
sdk/ATTRIBUTES.md                      # document langperf.completed
sdk/CHANGELOG.md                       # 0.3.0 entry
web/lib/api.ts                         # WorklistItem, MetricSeries, API fns
web/app/agents/[name]/[tab]/page.tsx   # Overview tab replacement
```

### Build order (why this sequence)

DB → SDK capture → Backend ingest/read → Web UI. Each task produces a meaningful commit and leaves the system working. The SDK's feedback function lands before the backend endpoint but the SDK retries silently, so order doesn't matter in production; we build the backend next so we can integration-test end-to-end quickly.

---

## Task 1: DB migration + Trajectory model columns

**Files:**
- Create: `api/alembic/versions/0017_feedback_and_completion.py`
- Modify: `api/app/models.py` — `Trajectory` class only

- [ ] **Step 1: Write the migration file**

Create `api/alembic/versions/0017_feedback_and_completion.py`:

```python
"""feedback counters + trajectory completed flag

Revision ID: 0017_feedback_and_completion
Revises: 0016_projects
Create Date: 2026-04-22 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_feedback_and_completion"
down_revision = "0016_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trajectories",
        sa.Column(
            "feedback_thumbs_down",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "trajectories",
        sa.Column(
            "feedback_thumbs_up",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "trajectories",
        sa.Column("completed", sa.Boolean, nullable=True),
    )
    op.create_index(
        "ix_trajectories_feedback_thumbs_down",
        "trajectories",
        ["feedback_thumbs_down"],
        postgresql_where=sa.text("feedback_thumbs_down > 0"),
    )


def downgrade() -> None:
    op.drop_index("ix_trajectories_feedback_thumbs_down", table_name="trajectories")
    op.drop_column("trajectories", "completed")
    op.drop_column("trajectories", "feedback_thumbs_up")
    op.drop_column("trajectories", "feedback_thumbs_down")
```

Rationale for the partial index: most trajectories never get thumbs-down, so the index only holds rows where the counter is non-zero — keeps it tiny and makes worklist feedback lookups O(hits).

- [ ] **Step 2: Add ORM columns to Trajectory**

In `api/app/models.py`, inside `class Trajectory(Base)`, after the `assigned_user_id` column (line 223), add:

```python
    feedback_thumbs_down: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    feedback_thumbs_up: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    completed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
```

Verify `Boolean` is imported from sqlalchemy near the top of the file. If not, add it to the existing import line:

```python
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
```

- [ ] **Step 3: Run migration + verify**

```bash
docker compose exec langperf-api alembic upgrade head
docker compose exec postgres psql -U langperf -d langperf -c "\d trajectories" | grep -E "feedback_thumbs|completed"
```

Expected: three new columns, default `0` on counters, `completed` nullable.

- [ ] **Step 4: Run existing api tests to confirm no breakage**

```bash
docker compose exec langperf-api python -m pytest -x -q
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add api/alembic/versions/0017_feedback_and_completion.py api/app/models.py
git commit -m "feat(db): trajectory feedback counters + completed flag"
```

---

## Task 2: Backend — ingest `langperf.completed` attribute

**Files:**
- Modify: `api/app/constants.py` — add `ATTR_COMPLETED`
- Modify: `api/app/otlp/ingest.py::_apply_sdk_signals` — read the attribute
- Create: `api/tests/test_completed_ingest.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_completed_ingest.py`:

```python
"""OTLP ingest reads `langperf.completed` off the trajectory-root span."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Trajectory


@pytest.mark.asyncio
async def test_completed_true_stamped_on_root_span(ingest_trajectory, session):
    traj_id = await ingest_trajectory(
        root_span_attrs={
            "langperf.node.kind": "trajectory",
            "langperf.completed": True,
        },
    )
    t = (await session.execute(select(Trajectory).where(Trajectory.id == traj_id))).scalar_one()
    assert t.completed is True


@pytest.mark.asyncio
async def test_completed_false_stamped_on_root_span(ingest_trajectory, session):
    traj_id = await ingest_trajectory(
        root_span_attrs={
            "langperf.node.kind": "trajectory",
            "langperf.completed": False,
        },
    )
    t = (await session.execute(select(Trajectory).where(Trajectory.id == traj_id))).scalar_one()
    assert t.completed is False


@pytest.mark.asyncio
async def test_completed_absent_stays_null(ingest_trajectory, session):
    traj_id = await ingest_trajectory(
        root_span_attrs={"langperf.node.kind": "trajectory"},
    )
    t = (await session.execute(select(Trajectory).where(Trajectory.id == traj_id))).scalar_one()
    assert t.completed is None


@pytest.mark.asyncio
async def test_completed_only_read_from_root_span(ingest_trajectory, session):
    """Non-root spans stamping `langperf.completed` must be ignored — the
    attribute is only meaningful on the trajectory root."""
    traj_id = await ingest_trajectory(
        root_span_attrs={"langperf.node.kind": "trajectory"},
        child_span_attrs={
            "langperf.node.kind": "llm",
            "langperf.completed": False,
        },
    )
    t = (await session.execute(select(Trajectory).where(Trajectory.id == traj_id))).scalar_one()
    assert t.completed is None
```

The `ingest_trajectory` fixture doesn't exist yet. Check `api/tests/test_otlp_sdk_signals.py` for the pattern — that test file exercises `_apply_sdk_signals` identically for `status_tag` / `notes`. Mirror its fixture. If that file uses a local helper instead of a fixture, pull the helper into `conftest.py` as a shared fixture or copy-paste it into this test file (the project convention is inline helpers if only one test needs it — copy-paste is fine).

- [ ] **Step 2: Run test, verify it fails**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_completed_ingest.py -v
```

Expected: all 4 tests FAIL (either `AttributeError: 'Trajectory' object has no attribute 'completed'` already passing because Task 1 added the column — in which case the tests fail asserting True/False rather than the column missing).

- [ ] **Step 3: Add constant**

In `api/app/constants.py`, near `ATTR_STATUS_TAG` / `ATTR_NOTES`:

```python
ATTR_COMPLETED = "langperf.completed"
```

- [ ] **Step 4: Extend `_apply_sdk_signals`**

In `api/app/otlp/ingest.py`:

1. Update the import line to include `ATTR_COMPLETED`:

```python
from app.constants import (
    ALLOWED_TAGS,
    ATTR_COMPLETED,
    ATTR_NODE_KIND,
    ATTR_NOTES,
    ATTR_STATUS_TAG,
)
```

2. Inside `_apply_sdk_signals`, after the existing `notes` block and before `return changed`, add:

```python
    completed = attrs.get(ATTR_COMPLETED)
    if isinstance(completed, bool) and trajectory.completed != completed:
        trajectory.completed = completed
        changed = True
```

Rationale for the `isinstance(..., bool)` guard: OTLP transports sometimes round-trip `True`/`False` through stringified forms. We only accept the native bool — a string `"true"` would indicate a misstamped attribute, and silently coercing it hides the bug.

- [ ] **Step 5: Run test to verify it passes**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_completed_ingest.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 6: Run full api test suite**

```bash
docker compose exec langperf-api python -m pytest -x -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add api/app/constants.py api/app/otlp/ingest.py api/tests/test_completed_ingest.py
git commit -m "feat(api): ingest langperf.completed into Trajectory.completed"
```

---

## Task 3: SDK — auto-stamp `langperf.completed` on trajectory exit

**Files:**
- Modify: `sdk/langperf/attributes.py` — add `COMPLETED` constant
- Modify: `sdk/langperf/trajectory.py` — stamp on `__exit__`
- Create: `sdk/tests/test_trajectory_completed.py`

- [ ] **Step 1: Write the failing test**

Create `sdk/tests/test_trajectory_completed.py`:

```python
"""Trajectory __exit__ stamps langperf.completed on the root span."""
from __future__ import annotations

import pytest

import langperf


def _root_completed(spans) -> bool | None:
    """Find the trajectory-root span in an exporter-flushed batch and
    return its completed attribute (None if absent)."""
    for span in spans:
        attrs = span.attributes or {}
        if attrs.get("langperf.node.kind") == "trajectory":
            return attrs.get("langperf.completed")
    return None


def test_clean_exit_stamps_completed_true(sdk_inited, exporter):
    with langperf.trajectory("ok-run"):
        pass
    langperf.flush()
    spans = exporter.get_finished_spans()
    assert _root_completed(spans) is True


def test_exception_exit_stamps_completed_false(sdk_inited, exporter):
    with pytest.raises(RuntimeError):
        with langperf.trajectory("bad-run"):
            raise RuntimeError("boom")
    langperf.flush()
    spans = exporter.get_finished_spans()
    assert _root_completed(spans) is False
```

The `sdk_inited` + `exporter` fixtures are in `sdk/tests/conftest.py` already — they wire up an `InMemorySpanExporter` and call `langperf.init()`. Do not invent new fixtures.

- [ ] **Step 2: Run test, verify it fails**

```bash
python -m pytest sdk/tests/test_trajectory_completed.py -v
```

Expected: both tests FAIL — the attribute is not set.

- [ ] **Step 3: Add SDK constant**

In `sdk/langperf/attributes.py`, after `NOTES = "langperf.notes"`:

```python
COMPLETED = "langperf.completed"
```

And add `"COMPLETED"` to the `__all__` list in the same file.

- [ ] **Step 4: Stamp the attribute in `__exit__`**

In `sdk/langperf/trajectory.py`, modify `_Trajectory.__exit__`:

```python
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            # Stamp completion BEFORE closing the span context. Otherwise
            # the span is already ended and the attribute silently drops.
            if self._span is not None:
                self._span.set_attribute(
                    "langperf.completed", exc_type is None
                )
            if self._span_cm is not None:
                self._span_cm.__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self._traj_span_token is not None:
                _TRAJECTORY_SPAN.reset(self._traj_span_token)
            if self._traj_id_token is not None:
                _TRAJECTORY_ID.reset(self._traj_id_token)
            if self._ctx_token is not None:
                context_api.detach(self._ctx_token)
```

Note: this intentionally uses the string literal `"langperf.completed"` (not `COMPLETED`) because `trajectory.py` imports from `langperf.attributes` only for baggage keys today; we avoid adding a new import to the hot path. If a later refactor consolidates imports, switch to the constant.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest sdk/tests/test_trajectory_completed.py -v
```

Expected: both tests PASS.

- [ ] **Step 6: Run full SDK test suite**

```bash
python -m pytest sdk/tests -q
```

Expected: all tests pass, no warnings about OTel provider reuse or span-after-end.

- [ ] **Step 7: Commit**

```bash
git add sdk/langperf/attributes.py sdk/langperf/trajectory.py sdk/tests/test_trajectory_completed.py
git commit -m "feat(sdk): stamp langperf.completed on trajectory __exit__"
```

---

## Task 4: SDK — `langperf.feedback()` function

**Files:**
- Create: `sdk/langperf/feedback.py`
- Modify: `sdk/langperf/__init__.py` — export `feedback`
- Create: `sdk/tests/test_feedback.py`

- [ ] **Step 1: Write the failing test**

Create `sdk/tests/test_feedback.py`:

```python
"""langperf.feedback() POST behavior + retry semantics."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import langperf


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LANGPERF_API_TOKEN", "lp_test0000_" + "x" * 32)
    monkeypatch.setenv("LANGPERF_ENDPOINT", "http://langperf-test:4318")


def _wait_for_calls(mock, n, timeout_s=2.0):
    """Poll until the mock has seen n calls or timeout elapses."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if mock.call_count >= n:
            return
        time.sleep(0.01)
    raise AssertionError(
        f"expected ≥{n} calls, got {mock.call_count} after {timeout_s}s"
    )


def test_feedback_posts_to_feedback_endpoint_with_bearer():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 204
        langperf.feedback("traj-123", thumbs="down")
        _wait_for_calls(mock_urlopen, 1)
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://langperf-test:4318/v1/feedback"
        assert req.get_header("Authorization").startswith("Bearer lp_test0000_")
        assert req.get_method() == "POST"


def test_feedback_includes_note_in_body():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 204
        langperf.feedback("traj-123", thumbs="up", note="loved it")
        _wait_for_calls(mock_urlopen, 1)
        req = mock_urlopen.call_args[0][0]
        import json as _json
        body = _json.loads(req.data)
        assert body == {"trajectory_id": "traj-123", "thumbs": "up", "note": "loved it"}


def test_feedback_retries_on_network_error_then_drops():
    import urllib.error
    attempts = []

    def boom(*args, **kwargs):
        attempts.append(time.monotonic())
        raise urllib.error.URLError("network down")

    with patch("urllib.request.urlopen", side_effect=boom):
        langperf.feedback("traj-123", thumbs="down")
        _wait_for_calls_attempts(attempts, 3)

    # Delays 0.25, 0.5, 1.0 s → total ~1.75s. Allow ≥1.4s (some jitter headroom)
    # and cap on the high side so a failing impl doesn't hang the suite.
    total = attempts[-1] - attempts[0]
    assert 1.4 <= total <= 2.5, f"expected retry pacing ~1.75s, got {total:.2f}"


def _wait_for_calls_attempts(lst, n, timeout_s=3.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if len(lst) >= n:
            return
        time.sleep(0.01)
    raise AssertionError(f"expected ≥{n} attempts, got {len(lst)}")


def test_feedback_never_raises_even_on_5xx():
    with patch("urllib.request.urlopen") as mock_urlopen:
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://langperf-test:4318/v1/feedback", 500, "boom", {}, None
        )
        # Must return without raising even after all retries exhaust
        langperf.feedback("traj-123", thumbs="down")
        _wait_for_calls(mock_urlopen, 3)


def test_feedback_rejects_invalid_thumbs():
    # Validation happens BEFORE the background thread kicks off so
    # developer-facing errors surface synchronously.
    with pytest.raises(ValueError, match="thumbs"):
        langperf.feedback("traj-123", thumbs="sideways")
```

- [ ] **Step 2: Run test, verify it fails**

```bash
python -m pytest sdk/tests/test_feedback.py -v
```

Expected: all tests FAIL — `langperf.feedback` is not importable.

- [ ] **Step 3: Write the implementation**

Create `sdk/langperf/feedback.py`:

```python
"""langperf.feedback(trajectory_id, thumbs, note=) — end-user thumbs capture.

Fire-and-forget HTTP POST to /v1/feedback. Three retries with 0.25/0.5/1s
backoff then silent drop. Never raises — a broken feedback pipe must never
break the calling application.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Literal, Optional

logger = logging.getLogger("langperf.feedback")

_VALID_THUMBS = ("up", "down")
_RETRY_DELAYS_S = (0.25, 0.5, 1.0)


def feedback(
    trajectory_id: str,
    *,
    thumbs: Literal["up", "down"],
    note: Optional[str] = None,
) -> None:
    """Record end-user thumbs feedback on a trajectory.

    Non-blocking: dispatches to a background thread and returns
    immediately. Retries the HTTP POST up to 3 times with exponential
    backoff (0.25/0.5/1s) then silently drops on persistent failure.

    Args:
        trajectory_id: UUID of the trajectory being rated. Typically you
            obtained this via `langperf.current_trajectory_id()` at the
            moment the agent responded, and stashed it next to the
            message so the user's thumbs click can reference it later.
        thumbs: "up" or "down". Other values raise ValueError synchronously
            so bad developer calls surface immediately.
        note: Optional free-form text reason. Appended to the trajectory's
            notes field server-side.
    """
    if thumbs not in _VALID_THUMBS:
        raise ValueError(
            f"thumbs must be one of {_VALID_THUMBS!r}, got {thumbs!r}"
        )

    token = os.environ.get("LANGPERF_API_TOKEN")
    endpoint = os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318")
    if not token:
        logger.warning("langperf.feedback: LANGPERF_API_TOKEN unset — dropping feedback")
        return

    body = {"trajectory_id": trajectory_id, "thumbs": thumbs}
    if note is not None:
        body["note"] = note

    thread = threading.Thread(
        target=_post_with_retries,
        args=(f"{endpoint.rstrip('/')}/v1/feedback", token, body),
        daemon=True,
        name="langperf-feedback",
    )
    thread.start()


def _post_with_retries(url: str, token: str, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    for i in range(len(_RETRY_DELAYS_S) + 1):
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 300:
                    return
                logger.warning(
                    "langperf.feedback: %s returned HTTP %d", url, resp.status
                )
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            logger.debug("langperf.feedback: attempt %d failed: %s", i + 1, exc)
        if i < len(_RETRY_DELAYS_S):
            time.sleep(_RETRY_DELAYS_S[i])
    logger.info("langperf.feedback: giving up after %d attempts", len(_RETRY_DELAYS_S) + 1)
```

- [ ] **Step 4: Export from package**

In `sdk/langperf/__init__.py`:

```python
from langperf.feedback import feedback
```

And add `"feedback"` to `__all__`.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest sdk/tests/test_feedback.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Run full SDK suite**

```bash
python -m pytest sdk/tests -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add sdk/langperf/feedback.py sdk/langperf/__init__.py sdk/tests/test_feedback.py
git commit -m "feat(sdk): add langperf.feedback(trajectory_id, thumbs, note)"
```

---

## Task 5: Backend — `POST /v1/feedback` endpoint

**Files:**
- Create: `api/app/api/feedback.py`
- Modify: `api/app/main.py` — register router
- Create: `api/tests/test_api_feedback.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_api_feedback.py`:

```python
"""POST /v1/feedback — bearer auth + trajectory ownership + counter increment."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Trajectory


@pytest.mark.asyncio
async def test_feedback_down_increments_counter(
    client, seed_agent_with_trajectory, session
):
    agent, traj = await seed_agent_with_trajectory()
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "down"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    assert r.status_code == 204
    refreshed = (
        await session.execute(select(Trajectory).where(Trajectory.id == traj.id))
    ).scalar_one()
    assert refreshed.feedback_thumbs_down == 1
    assert refreshed.feedback_thumbs_up == 0


@pytest.mark.asyncio
async def test_feedback_up_increments_counter(
    client, seed_agent_with_trajectory, session
):
    agent, traj = await seed_agent_with_trajectory()
    await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "up"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    refreshed = (
        await session.execute(select(Trajectory).where(Trajectory.id == traj.id))
    ).scalar_one()
    assert refreshed.feedback_thumbs_up == 1


@pytest.mark.asyncio
async def test_feedback_appends_note(client, seed_agent_with_trajectory, session):
    agent, traj = await seed_agent_with_trajectory(notes="initial")
    await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "down", "note": "wrong answer"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    refreshed = (
        await session.execute(select(Trajectory).where(Trajectory.id == traj.id))
    ).scalar_one()
    assert refreshed.notes is not None
    assert "initial" in refreshed.notes
    assert "wrong answer" in refreshed.notes


@pytest.mark.asyncio
async def test_feedback_rejects_missing_bearer(client, seed_agent_with_trajectory):
    _, traj = await seed_agent_with_trajectory()
    r = await client.post(
        "/v1/feedback", json={"trajectory_id": traj.id, "thumbs": "down"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_feedback_rejects_cross_agent(
    client, seed_agent_with_trajectory, seed_agent
):
    _, traj = await seed_agent_with_trajectory()
    other_agent = await seed_agent()  # different agent, same org
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "down"},
        headers={"Authorization": f"Bearer {other_agent.raw_token}"},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_feedback_404_on_missing_trajectory(client, seed_agent):
    agent = await seed_agent()
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": "00000000-0000-0000-0000-000000000000", "thumbs": "down"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_feedback_422_on_invalid_thumbs(client, seed_agent_with_trajectory):
    agent, traj = await seed_agent_with_trajectory()
    r = await client.post(
        "/v1/feedback",
        json={"trajectory_id": traj.id, "thumbs": "sideways"},
        headers={"Authorization": f"Bearer {agent.raw_token}"},
    )
    assert r.status_code == 422
```

`seed_agent_with_trajectory` and `seed_agent` fixtures: check `api/tests/conftest.py` — the existing `test_otlp_auth.py` file seeds an agent with a minted token. Pull the agent-seed helper into `conftest.py` as a fixture if not already there, and add `seed_agent_with_trajectory` that also creates a `Trajectory` row bound to that agent.

Fixture sketch (add to `api/tests/conftest.py`):

```python
@pytest.fixture
async def seed_agent(session):
    from app.auth.agent_token import generate_token, hash_token
    from app.models import Agent, Organization, Project
    import uuid
    org = (await session.execute(select(Organization).limit(1))).scalar_one_or_none()
    if org is None:
        org = Organization(id=str(uuid.uuid4()), name="test-org")
        session.add(org)
        await session.flush()
    proj = Project(id=str(uuid.uuid4()), org_id=org.id, name="Default", slug="default")
    session.add(proj)
    await session.flush()
    token, prefix = generate_token()
    agent = Agent(
        id=str(uuid.uuid4()),
        org_id=org.id,
        project_id=proj.id,
        name=f"test-agent-{uuid.uuid4().hex[:6]}",
        token_hash=hash_token(token),
        token_prefix=prefix,
    )
    session.add(agent)
    await session.commit()
    agent.raw_token = token  # type: ignore[attr-defined]  # test-only convenience
    return agent


@pytest.fixture
async def seed_agent_with_trajectory(session, seed_agent):
    async def _factory(*, notes: str | None = None):
        from app.models import Trajectory
        import uuid
        agent = await seed_agent()
        traj = Trajectory(
            id=str(uuid.uuid4()),
            org_id=agent.org_id,
            service_name=agent.name,
            agent_id=agent.id,
            notes=notes,
        )
        session.add(traj)
        await session.commit()
        return agent, traj
    return _factory
```

If `seed_agent` already exists as a fixture (check `api/tests/conftest.py` first), just add the `_with_trajectory` factory on top.

- [ ] **Step 2: Run tests, verify they fail**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_api_feedback.py -v
```

Expected: all tests FAIL — endpoint doesn't exist yet.

- [ ] **Step 3: Implement the router**

Create `api/app/api/feedback.py`:

```python
"""POST /v1/feedback — end-user thumbs-down/up capture.

Wire-format endpoint (lives under /v1/* to parallel /v1/traces) rather
than /api/* which is reserved for the web UI. Same bearer-token auth
pattern as OTLP ingest: the token's agent must own the target
trajectory or we 403.
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.agent_token import TOKEN_PREFIX_LEN, verify_token
from app.db import get_session
from app.models import Agent, Trajectory

logger = logging.getLogger("langperf.feedback")

router = APIRouter()


class FeedbackBody(BaseModel):
    trajectory_id: str = Field(min_length=1)
    thumbs: Literal["up", "down"]
    note: Optional[str] = Field(default=None, max_length=4000)


@router.post("/v1/feedback", status_code=204)
async def receive_feedback(
    payload: FeedbackBody,
    authorization: str | None = Header(default=None, alias="authorization"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    token = _extract_bearer(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="bearer token required")

    agent = await _resolve_agent_by_token(session, token)
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid token")

    traj = (
        await session.execute(
            select(Trajectory).where(Trajectory.id == payload.trajectory_id)
        )
    ).scalar_one_or_none()
    if traj is None:
        raise HTTPException(status_code=404, detail="trajectory not found")
    if traj.agent_id != agent.id:
        raise HTTPException(
            status_code=403,
            detail="trajectory does not belong to the authenticated agent",
        )

    if payload.thumbs == "down":
        traj.feedback_thumbs_down = (traj.feedback_thumbs_down or 0) + 1
    else:
        traj.feedback_thumbs_up = (traj.feedback_thumbs_up or 0) + 1

    if payload.note:
        # Append rather than overwrite so earlier SME / SDK notes survive.
        # Separator is blank line so markdown renderers treat entries as paragraphs.
        existing = traj.notes or ""
        separator = "\n\n" if existing else ""
        traj.notes = f"{existing}{separator}[👎 feedback] {payload.note}" if payload.thumbs == "down" else \
                     f"{existing}{separator}[👍 feedback] {payload.note}"

    session.add(traj)
    await session.commit()
    return Response(status_code=204)


def _extract_bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


async def _resolve_agent_by_token(session: AsyncSession, token: str) -> Agent | None:
    prefix = token[:TOKEN_PREFIX_LEN]
    row = (
        await session.execute(select(Agent).where(Agent.token_prefix == prefix))
    ).scalar_one_or_none()
    if row is None or row.token_hash is None:
        return None
    if not verify_token(token, row.token_hash):
        return None
    return row
```

- [ ] **Step 4: Register the router**

In `api/app/main.py`, alongside the existing `app.include_router` calls, add:

```python
from app.api import feedback as feedback_api
# ...
app.include_router(feedback_api.router)
```

- [ ] **Step 5: Run the tests**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_api_feedback.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Run full api suite**

```bash
docker compose exec langperf-api python -m pytest -x -q
```

- [ ] **Step 7: Commit**

```bash
git add api/app/api/feedback.py api/app/main.py api/tests/test_api_feedback.py api/tests/conftest.py
git commit -m "feat(api): POST /v1/feedback ingest for thumbs events"
```

---

## Task 6: Backend — `agent_timeseries` service + route

**Files:**
- Create: `api/app/services/agent_timeseries.py`
- Modify: `api/app/api/agents.py` — add route
- Create: `api/tests/test_agent_timeseries.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_agent_timeseries.py`:

```python
"""agent_timeseries compute — bucketed metric arrays."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.agent_timeseries import compute


@pytest.mark.asyncio
async def test_empty_agent_returns_zero_buckets(session, seed_agent):
    agent = await seed_agent()
    out = await compute(session, agent_id=agent.id, window="7d", metrics=["p95_latency"])
    assert len(out) == 1
    assert out[0]["metric"] == "p95_latency"
    assert out[0]["window"] == "7d"
    # Non-empty buckets list with zero-value entries across the window.
    assert len(out[0]["buckets"]) > 0
    assert all(b["value"] is None or b["value"] == 0 for b in out[0]["buckets"])


@pytest.mark.asyncio
async def test_p95_latency_reflects_trajectory_durations(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 2, "duration_ms": 500},
            {"started_at_minus_hours": 2, "duration_ms": 1500},
            {"started_at_minus_hours": 2, "duration_ms": 2500},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="24h", metrics=["p95_latency"])
    latency = out[0]
    # Find the bucket covering 2 hours ago and verify p95 ≥ 2400
    non_null = [b for b in latency["buckets"] if b["value"] is not None]
    assert non_null, "expected at least one non-null bucket"
    assert max(b["value"] for b in non_null) >= 2400


@pytest.mark.asyncio
async def test_feedback_metric_counts_thumbs_down_trajectories(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "feedback_thumbs_down": 2},
            {"started_at_minus_hours": 1, "feedback_thumbs_down": 0},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="24h", metrics=["feedback_down"])
    non_null = [b for b in out[0]["buckets"] if b["value"]]
    assert sum(b["value"] for b in non_null) == 1  # one trajectory with thumbs_down > 0


@pytest.mark.asyncio
async def test_step_ms_matches_window(session, seed_agent):
    agent = await seed_agent()
    out_24h = await compute(session, agent_id=agent.id, window="24h", metrics=["p95_latency"])
    out_7d = await compute(session, agent_id=agent.id, window="7d", metrics=["p95_latency"])
    out_30d = await compute(session, agent_id=agent.id, window="30d", metrics=["p95_latency"])
    assert out_24h[0]["step_ms"] == 5 * 60 * 1000         # 5-minute buckets
    assert out_7d[0]["step_ms"] == 60 * 60 * 1000         # 1-hour buckets
    assert out_30d[0]["step_ms"] == 6 * 60 * 60 * 1000    # 6-hour buckets


@pytest.mark.asyncio
async def test_completion_rate_excludes_null_completed(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "completed": True},
            {"started_at_minus_hours": 1, "completed": False},
            {"started_at_minus_hours": 1, "completed": None},  # legacy row, ignored
        ]
    )
    out = await compute(session, agent_id=agent.id, window="24h", metrics=["completion_rate"])
    non_null = [b for b in out[0]["buckets"] if b["value"] is not None]
    # denominator = 2 (completed + failed), numerator = 1 (completed)
    assert non_null[-1]["value"] == pytest.approx(0.5, abs=0.01)
```

Add `seed_agent_with_trajectories` fixture to `api/tests/conftest.py`:

```python
@pytest.fixture
async def seed_agent_with_trajectories(session, seed_agent):
    async def _factory(*, trajectories):
        from app.models import Trajectory
        import uuid
        from datetime import datetime, timedelta, timezone
        agent = await seed_agent()
        created = []
        now = datetime.now(timezone.utc)
        for spec in trajectories:
            started = now - timedelta(hours=spec.get("started_at_minus_hours", 0))
            traj = Trajectory(
                id=str(uuid.uuid4()),
                org_id=agent.org_id,
                service_name=agent.name,
                agent_id=agent.id,
                started_at=started,
                ended_at=started + timedelta(milliseconds=spec.get("duration_ms", 0) or 0),
                duration_ms=spec.get("duration_ms"),
                feedback_thumbs_down=spec.get("feedback_thumbs_down", 0),
                feedback_thumbs_up=spec.get("feedback_thumbs_up", 0),
                completed=spec.get("completed"),
            )
            session.add(traj)
            created.append(traj)
        await session.commit()
        agent._trajectories = created  # type: ignore
        return agent
    return _factory
```

- [ ] **Step 2: Run test, verify it fails**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_agent_timeseries.py -v
```

Expected: all FAIL — service doesn't exist.

- [ ] **Step 3: Implement the service**

Create `api/app/services/agent_timeseries.py`:

```python
"""Bucketed time-series metrics for an agent's detail page.

One service. Multiple metrics emitted per call, each with its own
bucket array. Buckets are aligned to epoch so two successive calls
with the same window return comparable arrays.

Step size derived from window:
    24h -> 5 minute buckets    (288 buckets)
    7d  -> 1 hour buckets      (168 buckets)
    30d -> 6 hour buckets      (120 buckets)

Supported metrics:
    p95_latency       — percentile 95 of trajectory.duration_ms per bucket
    cost_per_1k       — (we don't store cost today; returns None per bucket
                        until cost ingest lands; kept in the API so the
                        web client can request it without conditional logic)
    tool_success      — ok span count / total span count per bucket (span kind = tool)
    feedback_down     — count of trajectories with feedback_thumbs_down > 0 per bucket
    completion_rate   — completed_count / non_null_total per bucket
    token_efficiency  — sum(output_tokens) / sum(input_tokens) per bucket

Return shape per metric:
    {
      "metric":   "p95_latency",
      "window":   "7d",
      "step_ms":  3600000,
      "buckets": [{"ts_ms": 1761196800000, "value": 1420.3, "count": 88}, ...],
    }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Span, Trajectory

WINDOW_CONFIG = {
    "24h": {"hours": 24, "step_ms": 5 * 60 * 1000},
    "7d":  {"hours": 168, "step_ms": 60 * 60 * 1000},
    "30d": {"hours": 720, "step_ms": 6 * 60 * 60 * 1000},
}

SUPPORTED_METRICS = {
    "p95_latency",
    "cost_per_1k",
    "tool_success",
    "feedback_down",
    "completion_rate",
    "token_efficiency",
}


async def compute(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str,
    metrics: Iterable[str],
) -> list[dict[str, Any]]:
    cfg = WINDOW_CONFIG[window]
    now = datetime.now(timezone.utc)
    end = _bucket_floor(now, cfg["step_ms"])
    start = end - timedelta(hours=cfg["hours"])
    bucket_starts = _bucket_range(start, end, cfg["step_ms"])

    out: list[dict[str, Any]] = []
    for metric in metrics:
        if metric not in SUPPORTED_METRICS:
            raise ValueError(f"unsupported metric {metric!r}")
        series = await _compute_metric(
            session,
            agent_id=agent_id,
            metric=metric,
            bucket_starts=bucket_starts,
            step_ms=cfg["step_ms"],
        )
        out.append(
            {
                "metric": metric,
                "window": window,
                "step_ms": cfg["step_ms"],
                "buckets": series,
            }
        )
    return out


def _bucket_floor(ts: datetime, step_ms: int) -> datetime:
    epoch_ms = int(ts.timestamp() * 1000)
    floored_ms = (epoch_ms // step_ms) * step_ms
    return datetime.fromtimestamp(floored_ms / 1000, tz=timezone.utc)


def _bucket_range(start: datetime, end: datetime, step_ms: int) -> list[datetime]:
    step = timedelta(milliseconds=step_ms)
    out, cur = [], start
    while cur < end:
        out.append(cur)
        cur += step
    return out


async def _compute_metric(
    session: AsyncSession,
    *,
    agent_id: str,
    metric: str,
    bucket_starts: list[datetime],
    step_ms: int,
) -> list[dict[str, Any]]:
    # Skeleton: zero-fill then overlay real data.
    index = {b: i for i, b in enumerate(bucket_starts)}
    buckets = [{"ts_ms": int(b.timestamp() * 1000), "value": None, "count": 0} for b in bucket_starts]
    start = bucket_starts[0]
    end = bucket_starts[-1] + timedelta(milliseconds=step_ms)

    if metric == "p95_latency":
        rows = await _p95_latency_rows(session, agent_id, start, end, step_ms)
        for ts_ms, p95, count in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and count:
                buckets[i]["value"] = float(p95) if p95 is not None else None
                buckets[i]["count"] = int(count)

    elif metric == "tool_success":
        rows = await _tool_success_rows(session, agent_id, start, end, step_ms)
        for ts_ms, ok, total in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and total:
                buckets[i]["value"] = float(ok) / float(total)
                buckets[i]["count"] = int(total)

    elif metric == "feedback_down":
        rows = await _feedback_down_rows(session, agent_id, start, end, step_ms)
        for ts_ms, n in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None:
                buckets[i]["value"] = int(n)
                buckets[i]["count"] = int(n)

    elif metric == "completion_rate":
        rows = await _completion_rate_rows(session, agent_id, start, end, step_ms)
        for ts_ms, completed, total in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and total:
                buckets[i]["value"] = float(completed) / float(total)
                buckets[i]["count"] = int(total)

    elif metric == "token_efficiency":
        rows = await _token_efficiency_rows(session, agent_id, start, end, step_ms)
        for ts_ms, out_tok, in_tok in rows:
            i = _locate_bucket(ts_ms, index, step_ms)
            if i is not None and in_tok:
                buckets[i]["value"] = float(out_tok) / float(in_tok)
                buckets[i]["count"] = int(in_tok)

    elif metric == "cost_per_1k":
        # Cost not stored per trajectory today. Return the zero-filled
        # skeleton with null values so the client contract is stable.
        pass

    return buckets


def _locate_bucket(
    ts_ms: int, index: dict, step_ms: int
) -> int | None:
    bucket_ms = (ts_ms // step_ms) * step_ms
    bucket_dt = datetime.fromtimestamp(bucket_ms / 1000, tz=timezone.utc)
    return index.get(bucket_dt)


async def _p95_latency_rows(session, agent_id, start, end, step_ms):
    # Postgres: percentile_cont within each bucket. Portable SQL would use
    # a window function; here we group by explicit bucket key.
    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    stmt = select(
        bucket_sql.label("bucket_ms"),
        func.percentile_cont(0.95).within_group(Trajectory.duration_ms).label("p95"),
        func.count().label("count"),
    ).where(
        Trajectory.agent_id == agent_id,
        Trajectory.started_at >= start,
        Trajectory.started_at < end,
        Trajectory.duration_ms.isnot(None),
    ).group_by("bucket_ms").order_by("bucket_ms")
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.p95, r.count) for r in rows]


async def _tool_success_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Span.started_at, step_ms)
    ok_expr = func.sum(
        case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)
    ).label("ok")
    stmt = select(
        bucket_sql.label("bucket_ms"),
        ok_expr,
        func.count().label("total"),
    ).join(Trajectory, Trajectory.id == Span.trajectory_id).where(
        Trajectory.agent_id == agent_id,
        Span.started_at >= start,
        Span.started_at < end,
        Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
    ).group_by("bucket_ms").order_by("bucket_ms")
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.ok or 0, r.total or 0) for r in rows]


async def _feedback_down_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    stmt = select(
        bucket_sql.label("bucket_ms"),
        func.count().label("n"),
    ).where(
        Trajectory.agent_id == agent_id,
        Trajectory.started_at >= start,
        Trajectory.started_at < end,
        Trajectory.feedback_thumbs_down > 0,
    ).group_by("bucket_ms").order_by("bucket_ms")
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.n or 0) for r in rows]


async def _completion_rate_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    completed_expr = func.sum(
        case((Trajectory.completed.is_(True), 1), else_=0).cast(Integer)
    ).label("completed")
    total_expr = func.sum(
        case((Trajectory.completed.is_(None), 0), else_=1).cast(Integer)
    ).label("total")
    stmt = select(
        bucket_sql.label("bucket_ms"),
        completed_expr,
        total_expr,
    ).where(
        Trajectory.agent_id == agent_id,
        Trajectory.started_at >= start,
        Trajectory.started_at < end,
    ).group_by("bucket_ms").order_by("bucket_ms")
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.completed or 0, r.total or 0) for r in rows]


async def _token_efficiency_rows(session, agent_id, start, end, step_ms):
    bucket_sql = _sql_bucket_key(Trajectory.started_at, step_ms)
    stmt = select(
        bucket_sql.label("bucket_ms"),
        func.sum(Trajectory.output_tokens).label("out_tok"),
        func.sum(Trajectory.input_tokens).label("in_tok"),
    ).where(
        Trajectory.agent_id == agent_id,
        Trajectory.started_at >= start,
        Trajectory.started_at < end,
    ).group_by("bucket_ms").order_by("bucket_ms")
    rows = await session.execute(stmt)
    return [(int(r.bucket_ms), r.out_tok or 0, r.in_tok or 0) for r in rows]


def _sql_bucket_key(column, step_ms: int):
    """Return a SQL expression that floors `column` (a DateTime column) to a
    step-ms bucket and emits the bucket-start as an epoch-millisecond integer.

    Portable across sqlite and postgres: both accept EXTRACT(EPOCH FROM ts),
    which returns seconds as a float. Multiply to ms, divide, CAST to BIGINT,
    multiply back out. The CAST is what gives us floor semantics in both
    dialects (without it, sqlite does float division and the bucket edges
    drift).
    """
    epoch_ms = func.cast(func.extract("epoch", column) * 1000, Integer)
    return func.cast(epoch_ms / step_ms, Integer) * step_ms
```

Pass the actual mapped column into the helper, e.g. `_sql_bucket_key(Trajectory.started_at, step_ms)`. The helper is dialect-agnostic: both sqlite and postgres accept `EXTRACT(EPOCH FROM ts)`, and `CAST(... AS INTEGER)` gives us floor semantics on both.

If a test fails on sqlite with a type error around `extract("epoch", ...)`, the usual fix is making sure the column stores timezone-aware datetimes — the test fixtures use `datetime.now(timezone.utc)`, which preserves tzinfo through sqlite as long as the SQLAlchemy column was declared `DateTime(timezone=True)` (which our `Trajectory` is).

- [ ] **Step 4: Add the route**

In `api/app/api/agents.py`, add:

```python
from app.services import agent_timeseries
# ...

@router.get("/{name}/timeseries")
async def get_agent_timeseries(
    name: str,
    window: str = "7d",
    metrics: str = "p95_latency,cost_per_1k,tool_success,feedback_down",
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[dict]:
    if window not in agent_timeseries.WINDOW_CONFIG:
        raise HTTPException(status_code=400, detail=f"invalid window {window!r}")
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    unknown = [m for m in metric_list if m not in agent_timeseries.SUPPORTED_METRICS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown metrics {unknown}")

    agent = await agents_service.get_agent_by_name(session, user.org_id, name)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return await agent_timeseries.compute(
        session, agent_id=agent.id, window=window, metrics=metric_list
    )
```

If `agents_service.get_agent_by_name` doesn't exist, use the existing pattern in `agents.py` for looking up an agent by org + name (search for `Agent.name == name` in that file for the right helper).

- [ ] **Step 5: Run tests**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_agent_timeseries.py -v
```

Expected: all 5 tests PASS. If the sqlite bucketing fails due to type coercion, narrow `_sql_bucket_key` until it passes sqlite; percentile_cont quirks will surface in the postgres lane (Task 6.5 below).

- [ ] **Step 6: Run postgres lane (guards percentile_cont)**

```bash
docker compose exec -e DATABASE_URL=postgresql+asyncpg://langperf:langperf@postgres:5432/langperf langperf-api python -m pytest api/tests/test_agent_timeseries.py -v
```

Expected: all tests pass against postgres.

- [ ] **Step 7: Commit**

```bash
git add api/app/services/agent_timeseries.py api/app/api/agents.py api/tests/test_agent_timeseries.py api/tests/conftest.py
git commit -m "feat(api): agent timeseries service + GET /api/agents/:name/timeseries"
```

---

## Task 7: Backend — `agent_worklist` service + route

**Files:**
- Create: `api/app/services/agent_worklist.py`
- Modify: `api/app/api/agents.py` — add route
- Create: `api/tests/test_worklist_scoring.py`
- Create: `api/tests/test_worklist_e2e.py`

- [ ] **Step 1: Write the failing scoring-pure-function test**

Create `api/tests/test_worklist_scoring.py`:

```python
"""Scoring pure-function tests — no DB."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.agent_worklist import score, urgency_bucket, SEVERITY


def test_tool_error_beats_apology_phrase_at_same_count():
    now = datetime.now(timezone.utc)
    tool_err = score(SEVERITY["tool_error"], affected_runs=20, last_seen_at=now)
    apology  = score(SEVERITY["apology_phrase"], affected_runs=20, last_seen_at=now)
    assert tool_err > apology


def test_more_affected_runs_ranks_higher():
    now = datetime.now(timezone.utc)
    ten   = score(SEVERITY["tool_error"], affected_runs=10, last_seen_at=now)
    hundred = score(SEVERITY["tool_error"], affected_runs=100, last_seen_at=now)
    assert hundred > ten


def test_older_issue_decays():
    now = datetime.now(timezone.utc)
    fresh = score(SEVERITY["tool_error"], affected_runs=10, last_seen_at=now)
    week_old = score(
        SEVERITY["tool_error"],
        affected_runs=10,
        last_seen_at=now - timedelta(days=7),
    )
    # 1-week half-life → week-old should be ~half the score
    assert week_old < fresh
    assert 0.4 < week_old / fresh < 0.6


def test_urgency_buckets():
    assert urgency_bucket(10) == "high"
    assert urgency_bucket(6)  == "med"
    assert urgency_bucket(2)  == "low"
    assert urgency_bucket(8)  == "high"      # boundary ≥8
    assert urgency_bucket(4)  == "med"       # boundary ≥4
    assert urgency_bucket(3.9) == "low"
```

- [ ] **Step 2: Write the failing e2e test**

Create `api/tests/test_worklist_e2e.py`:

```python
"""Worklist end-to-end — seed signals, assert ranking."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.agent_worklist import compute


@pytest.mark.asyncio
async def test_empty_agent_returns_empty_list(session, seed_agent):
    agent = await seed_agent()
    out = await compute(session, agent_id=agent.id, window="7d")
    assert out == []


@pytest.mark.asyncio
async def test_tool_error_heuristic_surfaces(
    session, seed_agent_with_heuristic_hits
):
    agent = await seed_agent_with_heuristic_hits(
        hits=[{"kind": "tool_error", "tool_name": "search_orders", "count": 12}]
    )
    out = await compute(session, agent_id=agent.id, window="7d")
    assert len(out) >= 1
    top = out[0]
    assert top["signal"] == "heuristic:tool_error"
    assert "search_orders" in top["title"].lower()
    assert top["affected_runs"] == 12
    assert top["urgency"] in ("high", "med", "low")


@pytest.mark.asyncio
async def test_thumbs_down_surfaces(
    session, seed_agent_with_trajectories
):
    agent = await seed_agent_with_trajectories(
        trajectories=[
            {"started_at_minus_hours": 1, "feedback_thumbs_down": 1},
            {"started_at_minus_hours": 2, "feedback_thumbs_down": 3},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="7d")
    signals = [x["signal"] for x in out]
    assert "feedback:thumbs_down" in signals


@pytest.mark.asyncio
async def test_ranking_respects_severity_and_affected_runs(
    session, seed_agent_with_heuristic_hits
):
    agent = await seed_agent_with_heuristic_hits(
        hits=[
            {"kind": "apology_phrase", "tool_name": None, "count": 50},
            {"kind": "tool_error", "tool_name": "send_email", "count": 5},
        ]
    )
    out = await compute(session, agent_id=agent.id, window="7d")
    # tool_error (severity 3) with 5 hits should beat apology_phrase (severity 1) with 50
    # because 3 × log2(6) ≈ 7.75 > 1 × log2(51) ≈ 5.67
    assert out[0]["signal"] == "heuristic:tool_error"
```

Add `seed_agent_with_heuristic_hits` to `conftest.py`:

```python
@pytest.fixture
async def seed_agent_with_heuristic_hits(session, seed_agent):
    async def _factory(*, hits):
        from app.models import Trajectory, HeuristicHit
        import uuid
        from datetime import datetime, timezone
        agent = await seed_agent()
        # Need at least one trajectory per hit — heuristic_hits.trajectory_id
        # FKs back.
        now = datetime.now(timezone.utc)
        for spec in hits:
            for _ in range(spec["count"]):
                traj = Trajectory(
                    id=str(uuid.uuid4()),
                    org_id=agent.org_id,
                    service_name=agent.name,
                    agent_id=agent.id,
                    started_at=now,
                )
                session.add(traj)
                await session.flush()
                hit = HeuristicHit(
                    id=str(uuid.uuid4()),
                    trajectory_id=traj.id,
                    kind=spec["kind"],
                    severity=1,  # placeholder; worklist ignores this
                    tool_name=spec.get("tool_name"),
                    created_at=now,
                )
                session.add(hit)
        await session.commit()
        return agent
    return _factory
```

- [ ] **Step 3: Run both tests, verify they fail**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_worklist_scoring.py api/tests/test_worklist_e2e.py -v
```

Expected: FAIL — service missing.

- [ ] **Step 4: Implement the service**

Create `api/app/services/agent_worklist.py`:

```python
"""Agent worklist — ranked list of issues for the agent's detail page.

Pulls signals from heuristic hits, trajectory feedback counters,
window-vs-prior deltas on cost/latency/completion/tool-success, and
scores each candidate into a unified ranking.

Score formula (one pure function, exposed for direct unit tests):

    score = severity × log2(affected_runs + 1) × recency_decay(hours_since_last_seen)
    recency_decay(h) = 2 ** (-h / 168)    # 1-week half-life
    urgency:  ≥8 high, ≥4 med, else low
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HeuristicHit, Span, Trajectory


SEVERITY = {
    # heuristic-driven
    "tool_error":     3,
    "loop":           3,
    "latency_outlier": 2,
    "low_confidence": 2,
    "apology_phrase": 1,
    # feedback-driven
    "thumbs_down":    3,
    # delta-driven
    "cost_delta":     2,
    "latency_delta":  2,
    "completion_drop": 3,
    "tool_success_drop": 2,
}


WINDOW_HOURS = {"24h": 24, "7d": 168, "30d": 720}


@dataclass
class WorklistItem:
    signal: str                 # e.g. "heuristic:tool_error", "feedback:thumbs_down"
    title: str
    subtitle: str
    affected_runs: int
    last_seen_at: datetime
    severity: int
    score: float
    urgency: str                # "high" | "med" | "low"

    def as_dict(self) -> dict:
        d = asdict(self)
        d["last_seen_at"] = self.last_seen_at.isoformat()
        return d


def score(severity: int, affected_runs: int, last_seen_at: datetime) -> float:
    now = datetime.now(timezone.utc)
    hours_since = max(0.0, (now - last_seen_at).total_seconds() / 3600.0)
    decay = 2.0 ** (-hours_since / 168.0)
    return severity * math.log2(affected_runs + 1) * decay


def urgency_bucket(s: float) -> str:
    if s >= 8:
        return "high"
    if s >= 4:
        return "med"
    return "low"


async def compute(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str = "7d",
) -> list[dict]:
    hours = WINDOW_HOURS[window]
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)
    prior_start = now - timedelta(hours=2 * hours)

    items: list[WorklistItem] = []
    items.extend(await _heuristic_candidates(session, agent_id, window_start, now))
    items.extend(await _feedback_candidates(session, agent_id, window_start, now))
    items.extend(
        await _delta_candidates(session, agent_id, window_start, prior_start, now)
    )

    items.sort(key=lambda it: (-it.score, -it.last_seen_at.timestamp()))
    return [it.as_dict() for it in items[:20]]


async def _heuristic_candidates(
    session: AsyncSession,
    agent_id: str,
    window_start: datetime,
    now: datetime,
) -> list[WorklistItem]:
    stmt = (
        select(
            HeuristicHit.kind,
            HeuristicHit.tool_name,
            func.count().label("n"),
            func.max(HeuristicHit.created_at).label("last_seen"),
        )
        .join(Trajectory, Trajectory.id == HeuristicHit.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            HeuristicHit.created_at >= window_start,
        )
        .group_by(HeuristicHit.kind, HeuristicHit.tool_name)
    )
    rows = (await session.execute(stmt)).all()
    out: list[WorklistItem] = []
    for r in rows:
        sev = SEVERITY.get(r.kind, 1)
        s = score(sev, r.n, r.last_seen)
        title = (
            f"{r.kind.replace('_', ' ')} in `{r.tool_name}`"
            if r.tool_name
            else r.kind.replace("_", " ")
        )
        out.append(
            WorklistItem(
                signal=f"heuristic:{r.kind}",
                title=title,
                subtitle=f"{r.n} runs affected",
                affected_runs=r.n,
                last_seen_at=r.last_seen,
                severity=sev,
                score=s,
                urgency=urgency_bucket(s),
            )
        )
    return out


async def _feedback_candidates(
    session: AsyncSession,
    agent_id: str,
    window_start: datetime,
    now: datetime,
) -> list[WorklistItem]:
    stmt = select(
        func.count().label("n_trajs"),
        func.sum(Trajectory.feedback_thumbs_down).label("n_down"),
        func.max(Trajectory.started_at).label("last_seen"),
    ).where(
        Trajectory.agent_id == agent_id,
        Trajectory.started_at >= window_start,
        Trajectory.feedback_thumbs_down > 0,
    )
    row = (await session.execute(stmt)).one()
    if not row.n_trajs:
        return []
    sev = SEVERITY["thumbs_down"]
    affected = int(row.n_down or 0)
    s = score(sev, affected, row.last_seen or now)
    return [
        WorklistItem(
            signal="feedback:thumbs_down",
            title=f"{affected} thumbs-down events",
            subtitle=f"{row.n_trajs} trajectories flagged",
            affected_runs=affected,
            last_seen_at=row.last_seen or now,
            severity=sev,
            score=s,
            urgency=urgency_bucket(s),
        )
    ]


async def _delta_candidates(
    session: AsyncSession,
    agent_id: str,
    window_start: datetime,
    prior_start: datetime,
    now: datetime,
) -> list[WorklistItem]:
    out: list[WorklistItem] = []

    # p95 latency delta
    window_p95 = await _p95_latency(session, agent_id, window_start, now)
    prior_p95 = await _p95_latency(session, agent_id, prior_start, window_start)
    if window_p95 and prior_p95 and window_p95 / prior_p95 >= 1.25:
        sev = SEVERITY["latency_delta"]
        # We don't have per-item affected_runs for aggregate deltas; use
        # window's trajectory count as the proxy.
        affected = await _trajectory_count(session, agent_id, window_start, now)
        s = score(sev, max(1, affected), now)
        out.append(
            WorklistItem(
                signal="delta:latency",
                title=f"p95 latency climbed {((window_p95 / prior_p95) - 1) * 100:.0f}%",
                subtitle=f"{prior_p95:.0f}ms → {window_p95:.0f}ms (7d vs. prior 7d)",
                affected_runs=affected,
                last_seen_at=now,
                severity=sev,
                score=s,
                urgency=urgency_bucket(s),
            )
        )

    # Completion-rate drop (only if both windows have >= 10 trajectories)
    window_cr = await _completion_rate(session, agent_id, window_start, now)
    prior_cr = await _completion_rate(session, agent_id, prior_start, window_start)
    if window_cr is not None and prior_cr is not None and (prior_cr - window_cr) >= 0.05:
        sev = SEVERITY["completion_drop"]
        affected = await _trajectory_count(session, agent_id, window_start, now)
        s = score(sev, max(1, affected), now)
        out.append(
            WorklistItem(
                signal="delta:completion_drop",
                title=f"completion rate dropped {(prior_cr - window_cr) * 100:.1f}pp",
                subtitle=f"{prior_cr * 100:.0f}% → {window_cr * 100:.0f}%",
                affected_runs=affected,
                last_seen_at=now,
                severity=sev,
                score=s,
                urgency=urgency_bucket(s),
            )
        )

    # Per-tool success drops
    out.extend(await _tool_success_drops(session, agent_id, window_start, prior_start, now))
    return out


async def _p95_latency(session, agent_id, start, end):
    row = (
        await session.execute(
            select(
                func.percentile_cont(0.95).within_group(Trajectory.duration_ms)
            ).where(
                Trajectory.agent_id == agent_id,
                Trajectory.started_at >= start,
                Trajectory.started_at < end,
                Trajectory.duration_ms.isnot(None),
            )
        )
    ).scalar()
    return float(row) if row is not None else None


async def _trajectory_count(session, agent_id, start, end):
    return int(
        (
            await session.execute(
                select(func.count()).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= start,
                    Trajectory.started_at < end,
                )
            )
        ).scalar()
        or 0
    )


async def _completion_rate(session, agent_id, start, end):
    row = (
        await session.execute(
            select(
                func.sum(case((Trajectory.completed.is_(True), 1), else_=0).cast(Integer)),
                func.sum(case((Trajectory.completed.is_(None), 0), else_=1).cast(Integer)),
            ).where(
                Trajectory.agent_id == agent_id,
                Trajectory.started_at >= start,
                Trajectory.started_at < end,
            )
        )
    ).one()
    completed, total = row
    if not total or total < 10:
        return None
    return float(completed or 0) / float(total)


async def _tool_success_drops(session, agent_id, window_start, prior_start, now):
    # per-tool ok/total in each window, emit candidate per tool where
    # drop ≥ 5pp and window total ≥ 10.
    window_stats = await _tool_stats(session, agent_id, window_start, now)
    prior_stats = await _tool_stats(session, agent_id, prior_start, window_start)
    out: list[WorklistItem] = []
    for tool, (w_ok, w_total) in window_stats.items():
        if w_total < 10:
            continue
        p_ok, p_total = prior_stats.get(tool, (0, 0))
        if p_total == 0:
            continue
        w_rate = w_ok / w_total
        p_rate = p_ok / p_total
        drop = p_rate - w_rate
        if drop >= 0.05:
            sev = SEVERITY["tool_success_drop"]
            s = score(sev, w_total, now)
            out.append(
                WorklistItem(
                    signal=f"delta:tool_success:{tool}",
                    title=f"`{tool}` success dropped {drop * 100:.1f}pp",
                    subtitle=f"{p_rate * 100:.0f}% → {w_rate * 100:.0f}% ({w_total} calls)",
                    affected_runs=w_total,
                    last_seen_at=now,
                    severity=sev,
                    score=s,
                    urgency=urgency_bucket(s),
                )
            )
    return out


async def _tool_stats(session, agent_id, start, end):
    ok_expr = func.sum(
        case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)
    ).label("ok")
    total_expr = func.count().label("total")
    stmt = (
        select(
            Span.attributes["tool.name"].astext.label("tool"),
            ok_expr,
            total_expr,
        )
        .join(Trajectory, Trajectory.id == Span.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            Span.started_at >= start,
            Span.started_at < end,
            Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
        )
        .group_by("tool")
    )
    rows = (await session.execute(stmt)).all()
    return {r.tool: (int(r.ok or 0), int(r.total or 0)) for r in rows if r.tool}
```

- [ ] **Step 5: Add the route**

In `api/app/api/agents.py`:

```python
from app.services import agent_worklist
# ...

@router.get("/{name}/worklist")
async def get_agent_worklist(
    name: str,
    window: str = "7d",
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[dict]:
    if window not in agent_worklist.WINDOW_HOURS:
        raise HTTPException(status_code=400, detail=f"invalid window {window!r}")
    agent = await agents_service.get_agent_by_name(session, user.org_id, name)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return await agent_worklist.compute(session, agent_id=agent.id, window=window)
```

- [ ] **Step 6: Run the tests**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_worklist_scoring.py api/tests/test_worklist_e2e.py -v
```

Expected: all pass. If e2e fails on sqlite because of `percentile_cont`, run the postgres lane:

```bash
docker compose exec -e DATABASE_URL=postgresql+asyncpg://langperf:langperf@postgres:5432/langperf langperf-api python -m pytest api/tests/test_worklist_e2e.py -v
```

- [ ] **Step 7: Commit**

```bash
git add api/app/services/agent_worklist.py api/app/api/agents.py api/tests/test_worklist_scoring.py api/tests/test_worklist_e2e.py api/tests/conftest.py
git commit -m "feat(api): agent worklist service + GET /api/agents/:name/worklist"
```

---

## Task 8: Backend — `agent_profile` markdown service + route

**Files:**
- Create: `api/app/services/agent_profile.py`
- Modify: `api/app/api/agents.py` — add route
- Create: `api/tests/test_agent_profile_render.py`
- Create: `api/tests/fixtures/agent_profile/basic.md` (golden file)

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_agent_profile_render.py`:

```python
"""agent_profile.render_markdown — golden-file snapshot."""
from __future__ import annotations

import pathlib

import pytest

from app.services.agent_profile import render_markdown

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "agent_profile"


@pytest.mark.asyncio
async def test_render_matches_golden_basic(session, seed_agent_rich_history):
    agent = await seed_agent_rich_history()
    out = await render_markdown(session, agent_id=agent.id, window="7d")
    # Golden file; update with `python -m pytest ... --snapshot-update` if
    # we adopt a snapshot library. For now: exact-match.
    expected = (FIXTURES / "basic.md").read_text()
    assert out.strip() == expected.strip()


@pytest.mark.asyncio
async def test_render_handles_empty_agent(session, seed_agent):
    agent = await seed_agent()
    out = await render_markdown(session, agent_id=agent.id, window="7d")
    assert agent.name in out
    assert "No data in window" in out or "Snapshot" in out
```

Create `api/tests/fixtures/agent_profile/basic.md` (you'll generate this from the impl's first-run output — see Step 3 below).

Also add `seed_agent_rich_history` fixture to `conftest.py` — create an agent with a fixed set of trajectories + heuristic hits so the golden file is stable:

```python
@pytest.fixture
async def seed_agent_rich_history(session, seed_agent):
    async def _factory():
        from app.models import Trajectory, HeuristicHit, Span
        import uuid
        from datetime import datetime, timedelta, timezone
        agent = await seed_agent()
        now = datetime.now(timezone.utc)
        for i in range(10):
            traj = Trajectory(
                id=str(uuid.uuid4()),
                org_id=agent.org_id,
                service_name=agent.name,
                agent_id=agent.id,
                started_at=now - timedelta(hours=i),
                ended_at=now - timedelta(hours=i) + timedelta(milliseconds=1000 + i * 100),
                duration_ms=1000 + i * 100,
                completed=(i % 3 != 0),
                feedback_thumbs_down=1 if i < 3 else 0,
            )
            session.add(traj)
            if i < 4:
                session.add(HeuristicHit(
                    id=str(uuid.uuid4()),
                    trajectory_id=traj.id,
                    kind="tool_error",
                    severity=3,
                    tool_name="search_orders",
                    created_at=now - timedelta(hours=i),
                ))
        await session.commit()
        return agent
    return _factory
```

- [ ] **Step 2: Run test, verify it fails**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_agent_profile_render.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement the renderer**

Create `api/app/services/agent_profile.py`:

```python
"""Render a deterministic markdown profile of an agent.

Deterministic f-string template (no Jinja). Sections:
    1. Header (name + window)
    2. Snapshot — 4 KPIs with delta-vs-prior
    3. Top issues (top 5 worklist items)
    4. Tool landscape (top tools with ok% and p95)
    5. Recent patterns (failure-mode counts)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, HeuristicHit, Span, Trajectory, TrajectoryFailureMode
from app.services import agent_worklist


WINDOW_LABEL = {"24h": "24 hours", "7d": "7 days", "30d": "30 days"}


async def render_markdown(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str = "7d",
) -> str:
    agent = (
        await session.execute(select(Agent).where(Agent.id == agent_id))
    ).scalar_one()

    hours = agent_worklist.WINDOW_HOURS[window]
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)

    snapshot = await _snapshot(session, agent_id, window_start, now, hours)
    issues = await agent_worklist.compute(session, agent_id=agent_id, window=window)
    tools = await _tool_landscape(session, agent_id, window_start, now)
    patterns = await _pattern_counts(session, agent_id, window_start, now)

    parts: list[str] = []
    parts.append(f"# {agent.name}")
    parts.append(f"Window: last {WINDOW_LABEL[window]} ending {now.date().isoformat()}")
    parts.append("")

    parts.append("## Snapshot")
    if snapshot["runs"] == 0:
        parts.append("_No data in window._")
    else:
        parts.append(f"- runs: {snapshot['runs']}")
        parts.append(f"- p95 latency: {_fmt_ms(snapshot['p95'])}{_delta_str(snapshot['p95_delta'])}")
        parts.append(f"- tool success: {_fmt_pct(snapshot['tool_ok_rate'])}")
        parts.append(f"- user 👎: {snapshot['feedback_down']}")
    parts.append("")

    parts.append("## Top issues")
    if not issues:
        parts.append("_Nothing ranked high enough to surface._")
    else:
        for i, it in enumerate(issues[:5], start=1):
            parts.append(f"{i}. **{it['title']}** — {it['urgency']} urgency, {it['affected_runs']} affected")
    parts.append("")

    parts.append("## Tool landscape")
    if not tools:
        parts.append("_No tool calls in window._")
    else:
        parts.append("| tool | calls | ok % | p95 ms |")
        parts.append("| --- | --- | --- | --- |")
        for t in tools[:10]:
            parts.append(f"| `{t['name']}` | {t['calls']} | {_fmt_pct(t['ok_rate'])} | {_fmt_ms(t['p95'])} |")
    parts.append("")

    parts.append("## Recent patterns")
    if not patterns:
        parts.append("_No failure-mode tags in window._")
    else:
        for p in patterns:
            parts.append(f"- {p['tag']}: {p['count']}")

    return "\n".join(parts) + "\n"


async def _snapshot(session, agent_id, window_start, now, hours):
    prior_start = now - timedelta(hours=2 * hours)
    runs = int(
        (
            await session.execute(
                select(func.count()).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= window_start,
                )
            )
        ).scalar()
        or 0
    )
    p95 = (
        await session.execute(
            select(func.percentile_cont(0.95).within_group(Trajectory.duration_ms)).where(
                Trajectory.agent_id == agent_id,
                Trajectory.started_at >= window_start,
                Trajectory.duration_ms.isnot(None),
            )
        )
    ).scalar()
    p95_prior = (
        await session.execute(
            select(func.percentile_cont(0.95).within_group(Trajectory.duration_ms)).where(
                Trajectory.agent_id == agent_id,
                Trajectory.started_at >= prior_start,
                Trajectory.started_at < window_start,
                Trajectory.duration_ms.isnot(None),
            )
        )
    ).scalar()
    p95_delta = None
    if p95 is not None and p95_prior is not None and p95_prior > 0:
        p95_delta = (p95 / p95_prior) - 1.0

    tool_row = (
        await session.execute(
            select(
                func.sum(case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)),
                func.count(),
            )
            .join(Trajectory, Trajectory.id == Span.trajectory_id)
            .where(
                Trajectory.agent_id == agent_id,
                Span.started_at >= window_start,
                Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
            )
        )
    ).one()
    ok, total = tool_row
    tool_ok_rate = (ok or 0) / total if total else None

    fb_down = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(Trajectory.feedback_thumbs_down), 0)).where(
                    Trajectory.agent_id == agent_id,
                    Trajectory.started_at >= window_start,
                )
            )
        ).scalar()
        or 0
    )

    return {
        "runs": runs,
        "p95": float(p95) if p95 is not None else None,
        "p95_delta": p95_delta,
        "tool_ok_rate": tool_ok_rate,
        "feedback_down": fb_down,
    }


async def _tool_landscape(session, agent_id, window_start, now):
    ok_expr = func.sum(
        case((Span.status_code == "ERROR", 0), else_=1).cast(Integer)
    ).label("ok")
    stmt = (
        select(
            Span.attributes["tool.name"].astext.label("tool"),
            func.count().label("calls"),
            ok_expr,
            func.percentile_cont(0.95).within_group(Span.duration_ms).label("p95"),
        )
        .join(Trajectory, Trajectory.id == Span.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            Span.started_at >= window_start,
            Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
        )
        .group_by("tool")
        .order_by(func.count().desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "name": r.tool,
            "calls": int(r.calls),
            "ok_rate": float(r.ok or 0) / float(r.calls),
            "p95": float(r.p95) if r.p95 is not None else None,
        }
        for r in rows
        if r.tool
    ]


async def _pattern_counts(session, agent_id, window_start, now):
    stmt = (
        select(TrajectoryFailureMode.tag, func.count().label("n"))
        .join(Trajectory, Trajectory.id == TrajectoryFailureMode.trajectory_id)
        .where(
            Trajectory.agent_id == agent_id,
            TrajectoryFailureMode.created_at >= window_start,
        )
        .group_by(TrajectoryFailureMode.tag)
        .order_by(func.count().desc())
    )
    rows = (await session.execute(stmt)).all()
    return [{"tag": r.tag, "count": int(r.n)} for r in rows]


def _fmt_ms(v):
    if v is None:
        return "—"
    if v >= 1000:
        return f"{v / 1000:.2f}s"
    return f"{int(v)}ms"


def _fmt_pct(v):
    if v is None:
        return "—"
    return f"{v * 100:.1f}%"


def _delta_str(delta):
    if delta is None:
        return ""
    pct = delta * 100
    arrow = "↑" if pct > 0 else "↓"
    return f" ({arrow}{abs(pct):.0f}% vs. prior)"
```

- [ ] **Step 4: Generate the golden file**

Run the test once to produce the actual output, then capture it as the golden file:

```bash
# Temporarily weaken the test to print actual output
docker compose exec langperf-api python -c "
import asyncio
from app.services.agent_profile import render_markdown
from app.db import SessionLocal
from app.models import Agent
from sqlalchemy import select

async def main():
    async with SessionLocal() as s:
        a = (await s.execute(select(Agent).limit(1))).scalar_one()
        print(await render_markdown(s, agent_id=a.id, window='7d'))

asyncio.run(main())
"
```

Manually inspect the output for sanity (correct agent name, sensible numbers), then save it to `api/tests/fixtures/agent_profile/basic.md` — but make sure the numbers in the fixture match what `seed_agent_rich_history` produces, not arbitrary production data. The better path: run the test, copy the `out` the test prints into the fixture, run the test again — it should pass.

Alternative: change the initial test to write-through-capture mode:

```python
async def test_render_matches_golden_basic(session, seed_agent_rich_history, tmp_path):
    agent = await seed_agent_rich_history()
    out = await render_markdown(session, agent_id=agent.id, window="7d")
    golden_path = pathlib.Path(__file__).parent / "fixtures" / "agent_profile" / "basic.md"
    if not golden_path.exists():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(out)
        pytest.skip("golden file created — rerun")
    assert out.strip() == golden_path.read_text().strip()
```

Ship that with `SKIP` on first run and `PASS` after.

- [ ] **Step 5: Add the route**

In `api/app/api/agents.py`:

```python
from fastapi.responses import Response as FastAPIResponse
from app.services import agent_profile
# ...

@router.get("/{name}/profile.md")
async def get_agent_profile_md(
    name: str,
    window: str = "7d",
    session: AsyncSession = Depends(get_session),
    user=require_user(),
):
    agent = await agents_service.get_agent_by_name(session, user.org_id, name)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    body = await agent_profile.render_markdown(
        session, agent_id=agent.id, window=window
    )
    filename = f"agent-{agent.name}-profile.md"
    return FastAPIResponse(
        content=body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 6: Run tests**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_agent_profile_render.py -v
```

First run creates the golden file and skips. Run again — should pass.

- [ ] **Step 7: Commit**

```bash
git add api/app/services/agent_profile.py api/app/api/agents.py api/tests/test_agent_profile_render.py api/tests/fixtures/agent_profile/
git commit -m "feat(api): markdown agent profile + GET /api/agents/:name/profile.md"
```

---

## Task 9: Backend — `agent_failures` CSV service + route

**Files:**
- Create: `api/app/services/agent_failures.py`
- Modify: `api/app/api/agents.py` — add route
- Create: `api/tests/test_agent_failures_csv.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_agent_failures_csv.py`:

```python
"""agent_failures.render_csv — shape + filter correctness."""
from __future__ import annotations

import csv
import io

import pytest

from app.services.agent_failures import render_csv


@pytest.mark.asyncio
async def test_csv_has_expected_header(session, seed_agent_rich_history):
    agent = await seed_agent_rich_history()
    body = b""
    async for chunk in render_csv(session, agent_id=agent.id, window="7d",
                                   web_base_url="https://lp.example"):
        body += chunk
    reader = csv.reader(io.StringIO(body.decode()))
    header = next(reader)
    assert header == [
        "trajectory_id", "started_at", "heuristics", "tools_errored",
        "latency_ms", "cost_usd", "status_tag", "feedback_thumbs_down",
        "notes", "url",
    ]


@pytest.mark.asyncio
async def test_csv_includes_heuristic_flagged_row(session, seed_agent_rich_history):
    agent = await seed_agent_rich_history()
    body = b""
    async for chunk in render_csv(session, agent_id=agent.id, window="7d",
                                   web_base_url="https://lp.example"):
        body += chunk
    text = body.decode()
    # Fixture seeds 4 tool_error heuristic hits → at least 4 rows
    lines = [l for l in text.splitlines() if l]
    assert len(lines) >= 5  # header + 4 flagged rows


@pytest.mark.asyncio
async def test_csv_url_column_is_valid(session, seed_agent_rich_history):
    agent = await seed_agent_rich_history()
    body = b""
    async for chunk in render_csv(session, agent_id=agent.id, window="7d",
                                   web_base_url="https://lp.example"):
        body += chunk
    reader = csv.reader(io.StringIO(body.decode()))
    header = next(reader)
    rows = list(reader)
    for row in rows:
        url = row[header.index("url")]
        assert url.startswith("https://lp.example/t/")


@pytest.mark.asyncio
async def test_csv_empty_agent_returns_header_only(session, seed_agent):
    agent = await seed_agent()
    body = b""
    async for chunk in render_csv(session, agent_id=agent.id, window="7d",
                                   web_base_url="https://lp.example"):
        body += chunk
    lines = [l for l in body.decode().splitlines() if l]
    assert len(lines) == 1  # header only
```

- [ ] **Step 2: Run test, verify it fails**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_agent_failures_csv.py -v
```

- [ ] **Step 3: Implement the renderer**

Create `api/app/services/agent_failures.py`:

```python
"""Stream a CSV of flagged trajectories for an agent.

A trajectory qualifies if ANY of:
  - at least one HeuristicHit fired
  - feedback_thumbs_down > 0
  - status_tag in {"bad", "todo"}

Yields bytes chunks so FastAPI can stream directly into the HTTP response
without materializing the full CSV.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HeuristicHit, Span, Trajectory
from app.services import agent_worklist


HEADER = [
    "trajectory_id", "started_at", "heuristics", "tools_errored",
    "latency_ms", "cost_usd", "status_tag", "feedback_thumbs_down",
    "notes", "url",
]


async def render_csv(
    session: AsyncSession,
    *,
    agent_id: str,
    window: str = "7d",
    web_base_url: str,
) -> AsyncIterator[bytes]:
    hours = agent_worklist.WINDOW_HOURS[window]
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=hours)

    # Subquery: trajectory ids that have at least one heuristic hit in window
    hits_subq = (
        select(HeuristicHit.trajectory_id.label("tid"))
        .where(HeuristicHit.created_at >= window_start)
        .subquery()
    )
    tool_err_subq = (
        select(
            Span.trajectory_id.label("tid"),
            func.count().filter(Span.status_code == "ERROR").label("errored"),
        )
        .where(
            Span.started_at >= window_start,
            Span.attributes["langperf.node.kind"].astext.in_(["tool", "tool_call"]),
        )
        .group_by(Span.trajectory_id)
        .subquery()
    )

    stmt = (
        select(
            Trajectory.id,
            Trajectory.started_at,
            Trajectory.duration_ms,
            Trajectory.status_tag,
            Trajectory.feedback_thumbs_down,
            Trajectory.notes,
            tool_err_subq.c.errored,
        )
        .outerjoin(tool_err_subq, tool_err_subq.c.tid == Trajectory.id)
        .where(
            Trajectory.agent_id == agent_id,
            Trajectory.started_at >= window_start,
            or_(
                Trajectory.id.in_(select(hits_subq.c.tid)),
                Trajectory.feedback_thumbs_down > 0,
                Trajectory.status_tag.in_(["bad", "todo"]),
            ),
        )
        .order_by(Trajectory.started_at.desc())
    )

    # Pre-fetch heuristic kinds per trajectory so we can list them per row
    kinds_stmt = (
        select(
            HeuristicHit.trajectory_id,
            func.string_agg(HeuristicHit.kind, ",").label("kinds"),
        )
        .where(HeuristicHit.created_at >= window_start)
        .group_by(HeuristicHit.trajectory_id)
    )
    kinds_map = {
        r.trajectory_id: r.kinds
        for r in (await session.execute(kinds_stmt)).all()
    }

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    yield buf.getvalue().encode("utf-8")
    buf.seek(0)
    buf.truncate()

    rows = await session.execute(stmt)
    for r in rows:
        writer.writerow([
            r.id,
            r.started_at.isoformat() if r.started_at else "",
            kinds_map.get(r.id, ""),
            r.errored or 0,
            r.duration_ms or "",
            "",  # cost_usd — not stored today; left blank
            r.status_tag or "",
            r.feedback_thumbs_down or 0,
            (r.notes or "").replace("\n", " ").replace("\r", " "),
            f"{web_base_url.rstrip('/')}/t/{r.id}",
        ])
        yield buf.getvalue().encode("utf-8")
        buf.seek(0)
        buf.truncate()
```

Note: `func.string_agg` is Postgres-specific. For sqlite fall back to `group_concat`:

```python
# Dialect branch for portability. If tests run on sqlite,
# func.string_agg is unavailable; use group_concat instead.
agg = (
    func.group_concat(HeuristicHit.kind, ",")
    if session.bind.dialect.name == "sqlite"
    else func.string_agg(HeuristicHit.kind, ",")
)
```

- [ ] **Step 4: Add the route**

In `api/app/api/agents.py`:

```python
from fastapi.responses import StreamingResponse
from app.services import agent_failures
import os
# ...

@router.get("/{name}/failures.csv")
async def get_agent_failures_csv(
    name: str,
    window: str = "7d",
    session: AsyncSession = Depends(get_session),
    user=require_user(),
):
    agent = await agents_service.get_agent_by_name(session, user.org_id, name)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    base_url = os.environ.get("LANGPERF_WEB_BASE_URL", "http://localhost:3030")
    filename = f"agent-{agent.name}-failures.csv"
    return StreamingResponse(
        agent_failures.render_csv(
            session, agent_id=agent.id, window=window, web_base_url=base_url
        ),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 5: Run tests**

```bash
docker compose exec langperf-api python -m pytest api/tests/test_agent_failures_csv.py -v
```

- [ ] **Step 6: Commit**

```bash
git add api/app/services/agent_failures.py api/app/api/agents.py api/tests/test_agent_failures_csv.py
git commit -m "feat(api): agent failures CSV + GET /api/agents/:name/failures.csv"
```

---

## Task 10: Web — `SharedCursorProvider` context

**Files:**
- Create: `web/components/charts/shared-cursor.tsx`
- Create: `web/tests/unit/shared-cursor.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/tests/unit/shared-cursor.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { SharedCursorProvider, useSharedCursor } from "@/components/charts/shared-cursor";

function Reader() {
  const { hoverX } = useSharedCursor();
  return <div data-testid="read">{hoverX === null ? "null" : String(hoverX)}</div>;
}

function Writer() {
  const { setX } = useSharedCursor();
  return (
    <button
      data-testid="write"
      onClick={() => setX(42)}
    >
      set
    </button>
  );
}

describe("SharedCursorProvider", () => {
  it("starts with hoverX null", () => {
    render(
      <SharedCursorProvider>
        <Reader />
      </SharedCursorProvider>,
    );
    expect(screen.getByTestId("read").textContent).toBe("null");
  });

  it("sibling setX updates hoverX seen by Reader", () => {
    render(
      <SharedCursorProvider>
        <Reader />
        <Writer />
      </SharedCursorProvider>,
    );
    fireEvent.click(screen.getByTestId("write"));
    expect(screen.getByTestId("read").textContent).toBe("42");
  });

  it("useSharedCursor outside provider throws", () => {
    // Suppress expected error noise in the test output
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() =>
      render(<Reader />),
    ).toThrow(/SharedCursorProvider/);
    spy.mockRestore();
  });
});
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd web && npx vitest run tests/unit/shared-cursor.test.tsx
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the context**

Create `web/components/charts/shared-cursor.tsx`:

```tsx
"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

type SharedCursorValue = {
  hoverX: number | null;
  setX: (x: number | null) => void;
};

const Ctx = createContext<SharedCursorValue | null>(null);

export function SharedCursorProvider({ children }: { children: ReactNode }) {
  const [hoverX, setHoverX] = useState<number | null>(null);
  const setX = useCallback((x: number | null) => setHoverX(x), []);
  const value = useMemo(() => ({ hoverX, setX }), [hoverX, setX]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useSharedCursor(): SharedCursorValue {
  const v = useContext(Ctx);
  if (v == null) {
    throw new Error(
      "useSharedCursor must be used inside a <SharedCursorProvider>",
    );
  }
  return v;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd web && npx vitest run tests/unit/shared-cursor.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add web/components/charts/shared-cursor.tsx web/tests/unit/shared-cursor.test.tsx
git commit -m "feat(web): SharedCursorProvider context for synchronized chart cursors"
```

---

## Task 11: Web — `TrendChart` component

**Files:**
- Create: `web/components/charts/trend-chart.tsx`
- Create: `web/tests/unit/trend-chart.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/tests/unit/trend-chart.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, fireEvent, screen } from "@testing-library/react";
import { SharedCursorProvider } from "@/components/charts/shared-cursor";
import { TrendChart } from "@/components/charts/trend-chart";

const BUCKETS = [
  { ts_ms: 1_000_000, value: 1, count: 1 },
  { ts_ms: 2_000_000, value: 3, count: 2 },
  { ts_ms: 3_000_000, value: 2, count: 1 },
];

describe("TrendChart", () => {
  it("renders a polyline with one point per non-null bucket", () => {
    const { container } = render(
      <SharedCursorProvider>
        <TrendChart
          metric="p95_latency"
          buckets={BUCKETS}
          format={(v) => `${v}ms`}
          color="#6BBAB1"
        />
      </SharedCursorProvider>,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    const points = polyline!.getAttribute("points")!.trim().split(/\s+/);
    expect(points).toHaveLength(3);
  });

  it("skips null values without rendering them", () => {
    const data = [
      { ts_ms: 1_000_000, value: 1, count: 1 },
      { ts_ms: 2_000_000, value: null, count: 0 },
      { ts_ms: 3_000_000, value: 3, count: 2 },
    ];
    const { container } = render(
      <SharedCursorProvider>
        <TrendChart metric="x" buckets={data} format={(v) => `${v}`} color="#fff" />
      </SharedCursorProvider>,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline!.getAttribute("points")!.trim().split(/\s+/)).toHaveLength(2);
  });

  it("shows tooltip value on hover and hides on leave", () => {
    const { container } = render(
      <SharedCursorProvider>
        <TrendChart
          metric="p95_latency"
          buckets={BUCKETS}
          format={(v) => `${v}ms`}
          color="#6BBAB1"
        />
      </SharedCursorProvider>,
    );
    const surface = container.querySelector("[data-chart-surface]")!;
    fireEvent.mouseEnter(surface);
    fireEvent.mouseMove(surface, { clientX: 60, clientY: 60 });
    // Tooltip visible — any text matching `ms` shows up
    expect(screen.queryByText(/ms/)).not.toBeNull();
    fireEvent.mouseLeave(surface);
    expect(screen.queryByText(/ms/)).toBeNull();
  });
});
```

- [ ] **Step 2: Run, verify fail**

```bash
cd web && npx vitest run tests/unit/trend-chart.test.tsx
```

- [ ] **Step 3: Implement**

Create `web/components/charts/trend-chart.tsx`:

```tsx
"use client";

import { Fragment, useCallback, useLayoutEffect, useRef, useState } from "react";
import { useSharedCursor } from "./shared-cursor";

export type TrendBucket = {
  ts_ms: number;
  value: number | null;
  count: number;
};

type Props = {
  metric: string;
  buckets: TrendBucket[];
  format: (v: number) => string;
  color: string;
  height?: number;
  label?: string;
};

export function TrendChart({
  metric,
  buckets,
  format,
  color,
  height = 160,
  label,
}: Props) {
  const { hoverX, setX } = useSharedCursor();
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const [widthPx, setWidthPx] = useState<number>(0);

  useLayoutEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      setWidthPx(Math.max(0, w));
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // Build points in SVG coords: x is bucket index, y maps value → chart height.
  const chartH = height - 24; // leave room for x-axis time labels
  const maxY = Math.max(1, ...buckets.map((b) => b.value ?? 0));
  const step = buckets.length > 1 ? 240 / (buckets.length - 1) : 0;
  const toX = (i: number) => i * step;
  const toY = (v: number) => chartH - (v / maxY) * chartH;

  const segments: Array<Array<{ i: number; v: number }>> = [];
  let run: Array<{ i: number; v: number }> = [];
  buckets.forEach((b, i) => {
    if (b.value == null) {
      if (run.length) segments.push(run);
      run = [];
    } else {
      run.push({ i, v: b.value });
    }
  });
  if (run.length) segments.push(run);

  // Interpolate which bucket is under hoverX (in SVG units, 0..240)
  const hoverBucketIdx =
    hoverX != null && buckets.length > 1
      ? Math.min(buckets.length - 1, Math.max(0, Math.round(hoverX / step)))
      : null;
  const hoverBucket =
    hoverBucketIdx != null ? buckets[hoverBucketIdx] : null;

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!wrapRef.current || widthPx === 0) return;
      const rect = wrapRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      // map px → SVG x (0..240)
      const svgX = Math.max(0, Math.min(240, (x / widthPx) * 240));
      setX(svgX);
    },
    [setX, widthPx],
  );

  const onMouseLeave = useCallback(() => setX(null), [setX]);

  return (
    <div
      ref={wrapRef}
      data-chart-surface
      onMouseEnter={onMouseMove}
      onMouseMove={onMouseMove}
      onMouseLeave={onMouseLeave}
      className="relative"
      style={{ height }}
    >
      {label ? (
        <div className="absolute top-0 left-0 font-mono text-[9px] text-patina uppercase tracking-wider">
          {label}
        </div>
      ) : null}
      <svg
        viewBox={`0 0 240 ${chartH}`}
        preserveAspectRatio="none"
        className="w-full"
        style={{ height: chartH, marginTop: 14 }}
      >
        {segments.map((seg, si) => {
          if (seg.length === 1) {
            const p = seg[0];
            return (
              <circle key={si} cx={toX(p.i)} cy={toY(p.v)} r={1.5} fill={color} />
            );
          }
          const pts = seg.map((p) => `${toX(p.i)},${toY(p.v).toFixed(2)}`).join(" ");
          return (
            <polyline key={si} points={pts} fill="none" stroke={color} strokeWidth={1.5} />
          );
        })}
        {hoverX != null ? (
          <line
            x1={hoverX}
            x2={hoverX}
            y1={0}
            y2={chartH}
            stroke="rgba(167,139,250,0.8)"
            strokeWidth={1}
          />
        ) : null}
      </svg>
      {hoverBucket != null && hoverBucket.value != null ? (
        <div
          className="absolute pointer-events-none px-1.5 py-0.5 text-[10px] font-mono tabular-nums rounded text-aether-violet"
          style={{
            top: 0,
            left: `${(hoverX! / 240) * 100}%`,
            transform: "translateX(-50%)",
            background: "var(--surface)",
            border: "1px solid rgba(167,139,250,0.55)",
            whiteSpace: "nowrap",
          }}
        >
          {format(hoverBucket.value)}{" "}
          <span className="text-patina ml-1.5">
            {new Date(hoverBucket.ts_ms).toLocaleTimeString(undefined, {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
cd web && npx vitest run tests/unit/trend-chart.test.tsx
```

- [ ] **Step 5: Commit**

```bash
git add web/components/charts/trend-chart.tsx web/tests/unit/trend-chart.test.tsx
git commit -m "feat(web): TrendChart with shared cursor + violet hover tooltip"
```

---

## Task 12: Web — `AgentWorklist` component + client types

**Files:**
- Modify: `web/lib/api.ts` — add `WorklistItem` type + fetcher
- Create: `web/components/agent/worklist.tsx`

- [ ] **Step 1: Add client-side types + fetcher**

In `web/lib/api.ts`, add near the other agent-related types:

```ts
export type WorklistUrgency = "high" | "med" | "low";

export type WorklistItem = {
  signal: string;
  title: string;
  subtitle: string;
  affected_runs: number;
  last_seen_at: string;
  severity: number;
  score: number;
  urgency: WorklistUrgency;
};

export type MetricSeries = {
  metric: string;
  window: TimeWindow;
  step_ms: number;
  buckets: { ts_ms: number; value: number | null; count: number }[];
};

export async function getAgentWorklist(
  name: string,
  window: TimeWindow,
): Promise<WorklistItem[]> {
  const res = await fetch(
    `${apiBase()}/api/agents/${encodeURIComponent(name)}/worklist?window=${window}`,
    { cache: "no-store", credentials: "include" },
  );
  if (!res.ok) throw new Error(`getAgentWorklist ${res.status}`);
  return res.json();
}

export async function getAgentTimeseries(
  name: string,
  window: TimeWindow,
  metrics: string[],
): Promise<MetricSeries[]> {
  const q = metrics.join(",");
  const res = await fetch(
    `${apiBase()}/api/agents/${encodeURIComponent(name)}/timeseries?window=${window}&metrics=${q}`,
    { cache: "no-store", credentials: "include" },
  );
  if (!res.ok) throw new Error(`getAgentTimeseries ${res.status}`);
  return res.json();
}
```

- [ ] **Step 2: Implement the worklist component**

Create `web/components/agent/worklist.tsx`:

```tsx
"use client";

import Link from "next/link";
import type { WorklistItem } from "@/lib/api";

const URGENCY_COLOR: Record<WorklistItem["urgency"], string> = {
  high: "text-warn border-warn",
  med: "text-peach-neon border-peach-neon",
  low: "text-patina border-[color:var(--border)]",
};


export function AgentWorklist({
  agentName,
  items,
}: {
  agentName: string;
  items: WorklistItem[];
}) {
  if (items.length === 0) {
    return (
      <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[18px] text-center">
        <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[6px]">
          worklist
        </div>
        <div className="text-[12px] text-patina">
          Nothing ranked high enough to surface. Come back as data accumulates.
        </div>
      </div>
    );
  }
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)]">
      <div className="flex items-center justify-between px-[12px] py-[8px] border-b border-[color:var(--border)]">
        <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
          worklist · top {items.length}
        </span>
      </div>
      <ul>
        {items.map((it, i) => (
          <li
            key={`${it.signal}-${i}`}
            className="grid grid-cols-[28px_1fr_auto_auto] gap-[10px] items-center px-[12px] py-[10px] border-b border-[color:var(--border)]/50 last:border-b-0 hover:bg-warm-fog/[0.03]"
          >
            <span className="font-mono text-[10px] text-patina text-right">
              {i + 1}
            </span>
            <div className="min-w-0">
              <RowLink agentName={agentName} item={it} />
              <div className="text-[10px] text-patina truncate">{it.subtitle}</div>
            </div>
            <span
              className={`font-mono text-[9px] uppercase tracking-wider border rounded px-[6px] py-[1px] ${URGENCY_COLOR[it.urgency]}`}
            >
              {it.urgency}
            </span>
            <span className="font-mono text-[9px] text-patina tabular-nums">
              {it.affected_runs} runs
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}


function RowLink({ agentName, item }: { agentName: string; item: WorklistItem }) {
  const target = deriveTarget(agentName, item);
  if (target == null) {
    return <span className="text-[12px] text-warm-fog truncate block">{item.title}</span>;
  }
  return (
    <Link
      href={target}
      className="text-[12px] text-warm-fog hover:text-aether-teal truncate block"
    >
      {item.title}
    </Link>
  );
}


/**
 * Map a worklist item's signal to a pre-filterable destination page.
 * Not every signal has one yet — aggregate deltas (cost/latency) stay
 * informational in this phase.
 */
function deriveTarget(agentName: string, item: WorklistItem): string | null {
  if (item.signal.startsWith("heuristic:")) {
    const kind = item.signal.slice("heuristic:".length);
    return `/history?agent=${encodeURIComponent(agentName)}&heuristic=${kind}`;
  }
  if (item.signal === "feedback:thumbs_down") {
    return `/history?agent=${encodeURIComponent(agentName)}&feedback=down`;
  }
  return null;
}
```

- [ ] **Step 3: Commit**

```bash
git add web/lib/api.ts web/components/agent/worklist.tsx
git commit -m "feat(web): AgentWorklist component + worklist/timeseries client types"
```

No test for this task — the worklist is a thin renderer. It gets exercised by the Playwright spec in Task 14.

---

## Task 13: Web — `ExportBar` component

**Files:**
- Create: `web/components/agent/export-bar.tsx`

- [ ] **Step 1: Implement the component**

Create `web/components/agent/export-bar.tsx`:

```tsx
"use client";

import { apiBase } from "@/lib/api";

export function ExportBar({
  agentName,
  window,
}: {
  agentName: string;
  window: "24h" | "7d" | "30d";
}) {
  const base = apiBase();
  const agent = encodeURIComponent(agentName);
  return (
    <div className="flex items-center gap-[6px]">
      <a
        href={`${base}/api/agents/${agent}/profile.md?window=${window}`}
        download
        className="font-mono text-[10px] uppercase tracking-wider border border-peach-neon text-peach-neon rounded px-[8px] py-[3px] hover:bg-peach-neon/10"
      >
        ↓ profile.md
      </a>
      <a
        href={`${base}/api/agents/${agent}/failures.csv?window=${window}`}
        download
        className="font-mono text-[10px] uppercase tracking-wider border border-peach-neon text-peach-neon rounded px-[8px] py-[3px] hover:bg-peach-neon/10"
      >
        ↓ failures.csv
      </a>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/components/agent/export-bar.tsx
git commit -m "feat(web): ExportBar with profile.md + failures.csv download buttons"
```

---

## Task 14: Web — rewire Overview tab + Playwright specs

**Files:**
- Modify: `web/app/agents/[name]/[tab]/page.tsx` — new Overview body
- Create: `web/tests/agent-overview.spec.ts`
- Create: `web/tests/agent-exports.spec.ts`

- [ ] **Step 1: Write Playwright specs**

Create `web/tests/agent-overview.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("agent overview renders 4-chart grid with synchronized hover", async ({ page }) => {
  // Assume a seeded agent "reasoning-showcase" exists — see scripts/seed_demo_data.py.
  await page.goto("/agents/reasoning-showcase/overview");
  await expect(page.getByRole("link", { name: /agents/i }).first()).toBeVisible();
  const charts = page.locator("[data-chart-surface]");
  await expect(charts).toHaveCount(4);
  // Hovering one chart should surface a tooltip on every chart
  await charts.first().hover({ position: { x: 120, y: 40 } });
  const tooltips = page.locator("text=/\\d/").filter({ has: page.locator("span.text-patina") });
  // Exact selector is brittle — loosest check: at least 4 tooltip-ish elements
  // visible after hover. Tighten once component is stable.
  await expect(page.locator("text=/ms/")).toBeVisible();
});

test("worklist shows ranked items with urgency pills", async ({ page }) => {
  await page.goto("/agents/reasoning-showcase/overview");
  const worklist = page.locator("text=/worklist/i").first();
  await expect(worklist).toBeVisible();
  // Rows render; not asserting count because it depends on seeded data.
});
```

Create `web/tests/agent-exports.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test("profile.md download fires with correct Content-Disposition", async ({ page }) => {
  await page.goto("/agents/reasoning-showcase/overview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /profile\.md/i }).click(),
  ]);
  const filename = download.suggestedFilename();
  expect(filename).toMatch(/^agent-.+-profile\.md$/);
});

test("failures.csv download fires with correct Content-Disposition", async ({ page }) => {
  await page.goto("/agents/reasoning-showcase/overview");
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: /failures\.csv/i }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/^agent-.+-failures\.csv$/);
});
```

- [ ] **Step 2: Rewire the Overview tab**

In `web/app/agents/[name]/[tab]/page.tsx`:

1. Add imports at the top:

```ts
import { getAgentWorklist, getAgentTimeseries } from "@/lib/api";
import { SharedCursorProvider } from "@/components/charts/shared-cursor";
import { TrendChart } from "@/components/charts/trend-chart";
import { AgentWorklist } from "@/components/agent/worklist";
import { ExportBar } from "@/components/agent/export-bar";
```

2. Extend the Overview data fetch:

```ts
  let worklist: WorklistItem[] = [];
  let timeseries: MetricSeries[] = [];

  if (tab === "overview") {
    try {
      const [m, t, r, w, ts] = await Promise.all([
        getAgentMetrics(name, window),
        getAgentTools(name, window),
        getAgentRuns(name, { limit: 10 }),
        getAgentWorklist(name, window),
        getAgentTimeseries(name, window, [
          "p95_latency",
          "cost_per_1k",
          "tool_success",
          "feedback_down",
        ]),
      ]);
      metrics = m;
      tools = t;
      runs = r;
      worklist = w;
      timeseries = ts;
    } catch {
      // leave empties; page renders empty states
    }
  }
```

3. Replace the `tab === "overview"` branch body with:

```tsx
      {tab === "overview" ? (
        <>
          <div className="flex items-center justify-end mb-[10px]">
            <ExportBar agentName={name} window={window} />
          </div>

          <SharedCursorProvider>
            <div className="grid grid-cols-2 gap-[8px] mb-[10px]">
              <Card title={`p95 latency · ${window}`}>
                <TrendChart
                  metric="p95_latency"
                  buckets={seriesFor(timeseries, "p95_latency")}
                  format={(v) => (v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${Math.round(v)}ms`)}
                  color="#6BBAB1"
                />
              </Card>
              <Card title={`cost / 1k runs · ${window}`}>
                <TrendChart
                  metric="cost_per_1k"
                  buckets={seriesFor(timeseries, "cost_per_1k")}
                  format={(v) => `$${v.toFixed(3)}`}
                  color="#E8A87C"
                />
              </Card>
              <Card title={`tool success · ${window}`}>
                <TrendChart
                  metric="tool_success"
                  buckets={seriesFor(timeseries, "tool_success")}
                  format={(v) => `${(v * 100).toFixed(1)}%`}
                  color="#A78BFA"
                />
              </Card>
              <Card title={`user 👎 · ${window}`}>
                <TrendChart
                  metric="feedback_down"
                  buckets={seriesFor(timeseries, "feedback_down")}
                  format={(v) => String(Math.round(v))}
                  color="#D98A6A"
                />
              </Card>
            </div>
          </SharedCursorProvider>

          <AgentWorklist agentName={name} items={worklist} />

          <div className="h-[10px]" />

          <Card title="Recent runs" className="!p-0">
            <RunsTable rows={runs?.items ?? []} />
          </Card>
        </>
      ) : tab === "runs" ? (
        // ... existing ...
      )
```

4. Add the helper near the other utility fns (above the `AgentTab` component):

```ts
function seriesFor(series: MetricSeries[], metric: string) {
  return series.find((s) => s.metric === metric)?.buckets ?? [];
}
```

Also import `MetricSeries` and `WorklistItem` from `@/lib/api` alongside the other types.

- [ ] **Step 3: Run type check + lint**

```bash
cd web && npx tsc --noEmit
cd web && npx eslint app components lib
```

- [ ] **Step 4: Run vitest suite**

```bash
cd web && npx vitest run
```

Expected: all unit tests pass (including the new trend-chart / shared-cursor tests).

- [ ] **Step 5: Run Playwright**

Ensure the dev stack is up, then:

```bash
cd web && npx playwright test tests/agent-overview.spec.ts tests/agent-exports.spec.ts --project=chromium
```

If seeded data doesn't include a trajectory with reasoning/tool calls, fall back to a known-good agent slug in the specs (check `/agents` page for a seed agent name).

- [ ] **Step 6: Commit**

```bash
git add web/app/agents/[name]/[tab]/page.tsx web/tests/agent-overview.spec.ts web/tests/agent-exports.spec.ts
git commit -m "feat(web): wire agent Overview to trend grid + worklist + exports"
```

---

## Task 15: SDK — version bump, CHANGELOG, ATTRIBUTES.md

**Files:**
- Modify: `sdk/langperf/__init__.py` — `__version__ = "0.3.0"`
- Modify: `sdk/pyproject.toml` — `version = "0.3.0"`
- Modify: `sdk/CHANGELOG.md`
- Modify: `sdk/ATTRIBUTES.md`

- [ ] **Step 1: Bump versions**

In `sdk/langperf/__init__.py`:

```python
__version__ = "0.3.0"
```

In `sdk/pyproject.toml`:

```toml
version = "0.3.0"
```

- [ ] **Step 2: Document new attribute**

In `sdk/ATTRIBUTES.md`, under "SDK-side trajectory signals (root span only)", add a row to the existing table:

```markdown
| `langperf.completed` | bool | trajectory `__exit__` (auto) | Ingest → `Trajectory.completed` |
```

- [ ] **Step 3: Add CHANGELOG entry**

Prepend to `sdk/CHANGELOG.md`, above `## [0.2.1]`:

```markdown
## [0.3.0] — 2026-04-22

### Added
- `langperf.feedback(trajectory_id, thumbs, note=)` — record end-user
  thumbs-up/down feedback on a trajectory from the application. Fire-and-
  forget with 3-retry backoff; never raises. Bridges to
  `Trajectory.feedback_thumbs_down` / `_up` via the new `/v1/feedback`
  ingest endpoint.
- `langperf.completed` span attribute — the trajectory context manager
  now stamps `True` on clean exit and `False` if an exception propagates.
  Backend writes this to `Trajectory.completed` (null on legacy rows).
- Documented both in `ATTRIBUTES.md`.

### Notes
- Backend endpoints added in the same release: `POST /v1/feedback`,
  `GET /api/agents/:name/worklist`, `GET /api/agents/:name/timeseries`,
  `GET /api/agents/:name/profile.md`, `GET /api/agents/:name/failures.csv`.
```

- [ ] **Step 4: Verify nothing else drifted**

```bash
grep -E "^(__version__|version)" sdk/langperf/__init__.py sdk/pyproject.toml
```

Expected: both show `0.3.0`.

Run the full SDK suite one more time to make sure nothing in the bump broke imports:

```bash
python -m pytest sdk/tests -q
```

- [ ] **Step 5: Commit**

```bash
git add sdk/langperf/__init__.py sdk/pyproject.toml sdk/ATTRIBUTES.md sdk/CHANGELOG.md
git commit -m "chore(sdk): bump to 0.3.0 — feedback() + langperf.completed"
```

---

## Post-plan verification

After all 15 tasks complete, run the full gate-green checklist:

```bash
# Lint (pinned ruff)
docker compose exec langperf-api ruff check api/ sdk/

# Python tests — sqlite + postgres lanes
docker compose exec langperf-api python -m pytest -q
docker compose exec -e DATABASE_URL=postgresql+asyncpg://langperf:langperf@postgres:5432/langperf langperf-api python -m pytest -q

# SDK tests (zero backend)
python -m pytest sdk/tests -q

# Web
cd web && npx tsc --noEmit && npx eslint app components lib && npx vitest run

# Playwright (manual; not in CI yet)
cd web && npx playwright test --project=chromium
```

Visual smoke: open `http://localhost:3030/agents/<seed-agent>/overview` and confirm:
1. Four charts render in a 2×2 grid
2. Moving the mouse over any chart draws a violet vertical cursor on all four, with each chart showing its own value-at-timestamp tooltip
3. Worklist renders below with ranked items
4. Clicking `↓ profile.md` downloads a file matching `agent-<name>-profile.md`
5. Clicking `↓ failures.csv` downloads a file matching `agent-<name>-failures.csv`

---

## Execution notes for the implementing agent

- **Work one task at a time.** Each is 30–90 minutes max for a focused slice. Commit after every task — if something goes sideways, the previous commit is a clean rollback point.
- **TDD is not optional here.** Every task lists a failing test first, then the implementation. Do not write the implementation before confirming the test fails for the expected reason.
- **Ruff is pinned.** If lint complains, do not upgrade ruff — the pin in CI will flag it. Fix the code.
- **Append-only migrations.** The migration in Task 1 is new. Do not edit it after commit; if you need corrections, add `0018_*` with the fix.
- **SDK discipline.** Per `CLAUDE.md`, the SDK has no backend imports. Task 4's `feedback.py` uses only `urllib` and stdlib. Keep it that way.
- **Mirror attribute constants.** Task 3 adds `COMPLETED` to `sdk/langperf/attributes.py`; Task 2 adds `ATTR_COMPLETED` to `api/app/constants.py`. Values must match (`"langperf.completed"`) — this is the wire-protocol contract.
- **Ordering choice.** Tasks are written to be completable in order, but Task 4 (SDK feedback) can go in parallel with Tasks 6–9 (backend routes) — there's no shared state between them.
