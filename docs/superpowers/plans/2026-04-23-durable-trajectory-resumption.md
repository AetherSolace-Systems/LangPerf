# Durable Trajectory Resumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add caller-provided `id` and `final` kwargs to `langperf.trajectory(...)` so a single logical run can accumulate spans across process boundaries, and teach the web UI to render multi-segment trajectories as stacked segment subtrees with idle-gap labels.

**Architecture:** SDK validates a caller-supplied UUID and reuses it across resumptions; `final=False` skips `langperf.completed` stamping so early/intermediate segments don't prematurely finalize the row. No backend schema or ingest code changes — ingest already upserts by `trajectory.id` and already tolerates multiple root spans. Web UI derives segments as `kind=trajectory` root spans ordered by `started_at`, rendering dividers labeled with human-readable gaps between them.

**Tech Stack:** Python 3.12 + pytest (SDK), async SQLAlchemy + pytest (API), Next.js 14 + TypeScript + vitest + @testing-library/react (web).

**Spec reference:** `docs/superpowers/specs/2026-04-23-durable-trajectory-resumption-design.md`

---

## File Structure

**Modified:**
- `sdk/langperf/trajectory.py` — add `id` and `final` kwargs to `_Trajectory.__init__`; validate UUID; skip `COMPLETED` stamping when `final=False`.
- `sdk/ATTRIBUTES.md` — document caller-settable `langperf.trajectory.id` and multi-segment semantics.
- `sdk/CHANGELOG.md` — new `[0.4.0]` entry.
- `sdk/langperf/__init__.py` — bump `__version__` to `"0.4.0"`.
- `sdk/pyproject.toml` — bump `version` to `"0.4.0"`.
- `sdk/README.md` — append "Durable trajectories" section with Temporal and plain-Python examples.
- `web/lib/format.ts` — add `fmtDurationHuman(ms)` helper (handles ms → seconds → minutes → hours → days).
- `web/components/trajectory-tree.tsx` — split roots into segments (`kind=trajectory` roots), render dividers between them.
- `web/components/trajectory-timeline.tsx` — render dashed idle-gap band between segments (gap > 1s).

**Created:**
- `sdk/tests/test_trajectory_resume.py` — SDK tests for `id` and `final` kwargs.
- `api/tests/test_otlp_resume.py` — API confidence tests for multi-segment ingest (no code change expected).
- `web/lib/segments.ts` — `buildSegments(spans)` helper; identifies `kind=trajectory` roots and associates each span with its segment.
- `web/tests/unit/segments.test.ts` — unit tests for `buildSegments`.
- `web/tests/unit/format-duration-human.test.ts` — unit tests for `fmtDurationHuman`.
- `web/tests/unit/trajectory-tree.test.tsx` — rendering tests for multi-segment tree.
- `examples/durable_agent.py` — runnable example (plain-Python queue-based resumption).

---

## Task 1: SDK — caller-provided `id` kwarg

**Files:**
- Modify: `sdk/langperf/trajectory.py:60-94`
- Test: `sdk/tests/test_trajectory_resume.py` (create)

- [ ] **Step 1: Write failing test — `id` kwarg is used verbatim**

Create `sdk/tests/test_trajectory_resume.py`:

```python
"""Caller-provided trajectory.id and `final` kwarg — durable resumption support."""
from __future__ import annotations

import uuid

import pytest

import langperf
from langperf.attributes import NODE_KIND, TRAJECTORY_ID

from .conftest import finished_spans


def test_caller_provided_id_used_verbatim(exporter):
    run_id = str(uuid.uuid4())
    with langperf.trajectory("seg-1", id=run_id) as t:
        pass

    assert t.id == run_id
    root = finished_spans(exporter)[0]
    assert root.attributes[TRAJECTORY_ID] == run_id


def test_caller_provided_id_propagates_to_children(exporter):
    run_id = str(uuid.uuid4())
    with langperf.trajectory("seg-1", id=run_id):
        with langperf.node(kind="tool", name="inner"):
            pass
    spans = finished_spans(exporter)
    by_name = {s.name: s for s in spans}
    assert by_name["seg-1"].attributes[TRAJECTORY_ID] == run_id
    assert by_name["inner"].attributes[TRAJECTORY_ID] == run_id


def test_invalid_id_raises_value_error(exporter):
    with pytest.raises(ValueError):
        with langperf.trajectory("bad-id", id="not-a-uuid"):
            pass
    # No root span was opened because __enter__ raised before the span.
    assert finished_spans(exporter) == []


def test_two_sequential_blocks_sharing_id_emit_two_roots(exporter):
    run_id = str(uuid.uuid4())
    with langperf.trajectory("run", id=run_id):
        pass
    with langperf.trajectory("run", id=run_id):
        pass
    roots = [
        s
        for s in finished_spans(exporter)
        if s.attributes.get(NODE_KIND) == "trajectory"
    ]
    assert len(roots) == 2
    assert {r.attributes[TRAJECTORY_ID] for r in roots} == {run_id}


def test_default_behavior_unchanged_when_id_not_provided(exporter):
    """Regression guard: omitting `id=` must still autogenerate a UUID."""
    with langperf.trajectory("auto") as t:
        pass
    assert uuid.UUID(t.id)  # parses cleanly
    root = finished_spans(exporter)[0]
    assert root.attributes[TRAJECTORY_ID] == t.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest sdk/tests/test_trajectory_resume.py -v`
Expected: `test_caller_provided_id_used_verbatim`, `test_caller_provided_id_propagates_to_children`, `test_invalid_id_raises_value_error`, `test_two_sequential_blocks_sharing_id_emit_two_roots` all FAIL with `TypeError: __init__() got an unexpected keyword argument 'id'`. `test_default_behavior_unchanged_when_id_not_provided` PASSES.

- [ ] **Step 3: Add `id` kwarg to `_Trajectory.__init__`**

Edit `sdk/langperf/trajectory.py`. Modify the `__init__` signature and body:

```python
    def __init__(
        self,
        name: Optional[str] = None,
        *,
        id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ):
        # Caller-provided IDs must be UUID-parseable — ingest expects
        # canonical UUID form and rejects anything else. Fail loud at
        # __enter__ (practically here) rather than silently downstream.
        if id is not None:
            self.id: str = str(uuid.UUID(id))
        else:
            self.id = str(uuid.uuid4())
        self.name: Optional[str] = name
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = dict(metadata) if metadata else None
        self._ctx_token = None
        self._span_cm = None
        self._span = None
        self._traj_span_token = None
        self._traj_id_token = None
```

- [ ] **Step 4: Run tests to verify `id` path passes**

Run: `pytest sdk/tests/test_trajectory_resume.py::test_caller_provided_id_used_verbatim sdk/tests/test_trajectory_resume.py::test_caller_provided_id_propagates_to_children sdk/tests/test_trajectory_resume.py::test_invalid_id_raises_value_error sdk/tests/test_trajectory_resume.py::test_two_sequential_blocks_sharing_id_emit_two_roots sdk/tests/test_trajectory_resume.py::test_default_behavior_unchanged_when_id_not_provided -v`
Expected: all 5 PASS.

- [ ] **Step 5: Full SDK test suite green**

Run: `pytest sdk/tests -q`
Expected: all SDK tests pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add sdk/langperf/trajectory.py sdk/tests/test_trajectory_resume.py
git commit -m "$(cat <<'EOF'
feat(sdk): accept caller-provided trajectory id

Enables durable/resumable agents to thread multiple process segments
into one Trajectory row by passing a stable `id=` kwarg on each
`with langperf.trajectory(...)` block. Invalid UUIDs raise ValueError
at __enter__.
EOF
)"
```

---

## Task 2: SDK — `final` kwarg skips completion stamping

**Files:**
- Modify: `sdk/langperf/trajectory.py:60-77, 109-123`
- Test: `sdk/tests/test_trajectory_resume.py` (append)

- [ ] **Step 1: Append failing tests for `final`**

First, update the import block at the top of `sdk/tests/test_trajectory_resume.py` to include `COMPLETED`:

```python
from langperf.attributes import COMPLETED, NODE_KIND, TRAJECTORY_ID
```

Then append these tests to the same file:

```python
def test_final_false_does_not_stamp_completed(exporter):
    with langperf.trajectory("seg-mid", final=False):
        pass
    root = finished_spans(exporter)[0]
    assert COMPLETED not in root.attributes


def test_final_false_does_not_stamp_completed_on_exception(exporter):
    with pytest.raises(RuntimeError):
        with langperf.trajectory("seg-mid-fail", final=False):
            raise RuntimeError("mid-segment boom")
    root = finished_spans(exporter)[0]
    # Even on exception, non-final segment leaves completed unset so a
    # later final segment can authoritatively stamp the run's outcome.
    assert COMPLETED not in root.attributes


def test_final_true_default_still_stamps_completed(exporter):
    with langperf.trajectory("seg-final"):
        pass
    root = finished_spans(exporter)[0]
    assert root.attributes[COMPLETED] is True


def test_final_true_stamps_false_on_exception(exporter):
    with pytest.raises(RuntimeError):
        with langperf.trajectory("seg-final-fail", final=True):
            raise RuntimeError("boom")
    root = finished_spans(exporter)[0]
    assert root.attributes[COMPLETED] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest sdk/tests/test_trajectory_resume.py -v -k final`
Expected: `test_final_false_does_not_stamp_completed`, `test_final_false_does_not_stamp_completed_on_exception` FAIL with `TypeError: __init__() got an unexpected keyword argument 'final'`. `test_final_true_default_still_stamps_completed`, `test_final_true_stamps_false_on_exception` FAIL for the same reason.

- [ ] **Step 3: Add `final` kwarg and gate `COMPLETED` stamping**

Edit `sdk/langperf/trajectory.py`. Update `__init__` signature + `__slots__` + `__exit__`:

Add `"final"` to `__slots__`:

```python
    __slots__ = (
        "id",
        "name",
        "user_id",
        "session_id",
        "metadata",
        "final",
        "_ctx_token",
        "_span_cm",
        "_span",
        "_traj_span_token",
        "_traj_id_token",
    )
```

Update `__init__` to accept and store `final`:

```python
    def __init__(
        self,
        name: Optional[str] = None,
        *,
        id: Optional[str] = None,
        final: bool = True,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ):
        if id is not None:
            self.id: str = str(uuid.UUID(id))
        else:
            self.id = str(uuid.uuid4())
        self.name: Optional[str] = name
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = dict(metadata) if metadata else None
        self.final = final
        self._ctx_token = None
        self._span_cm = None
        self._span = None
        self._traj_span_token = None
        self._traj_id_token = None
```

Update `__exit__` to gate `COMPLETED` stamping on `self.final`:

```python
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            # Stamp completion BEFORE closing the span context. Otherwise
            # the span is already ended and the attribute silently drops.
            # Only the final segment of a durable run stamps completion —
            # non-final segments leave the Trajectory row's `completed`
            # column untouched so intermediate success/failure doesn't
            # prematurely finalize a run that continues in a later segment.
            if self._span is not None and self.final:
                self._span.set_attribute(COMPLETED, exc_type is None)
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest sdk/tests/test_trajectory_resume.py -v`
Expected: all 9 tests PASS.

- [ ] **Step 5: Full SDK test suite green**

Run: `pytest sdk/tests -q`
Expected: all SDK tests pass. In particular, `sdk/tests/test_trajectory_completed.py` must still pass — it exercises the `final=True` default path.

- [ ] **Step 6: Lint**

Run: `ruff check sdk/`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add sdk/langperf/trajectory.py sdk/tests/test_trajectory_resume.py
git commit -m "$(cat <<'EOF'
feat(sdk): add final= kwarg to skip completion stamping

Non-final trajectory segments (final=False) no longer stamp
langperf.completed on __exit__, so a durable run's Trajectory.completed
only finalizes when the last segment closes. Required companion to the
caller-provided id= kwarg for durable/resumable agents.
EOF
)"
```

---

## Task 3: SDK — update ATTRIBUTES.md

**Files:**
- Modify: `sdk/ATTRIBUTES.md:25-34`

- [ ] **Step 1: Update the trajectory-identity table and add a durable-resumption note**

Edit `sdk/ATTRIBUTES.md`. Replace the "Trajectory identity (span-level)" section (lines 25–34) with:

```markdown
## Trajectory identity (span-level)

Stamped on every span produced inside a `with langperf.trajectory(...)`
block. Baggage-propagated, so OpenInference-emitted spans inherit these
without explicit threading.

| Key | Type | Written by | Read by |
| --- | --- | --- | --- |
| `langperf.trajectory.id` | UUID string | `trajectory()` (baggage) — autogenerated by default; may be caller-supplied via `trajectory(id=)` | Ingest → `Trajectory.id` |
| `langperf.trajectory.name` | string | `trajectory(name=)` | Ingest → `Trajectory.name` |

### Durable resumption

Callers running multi-process / resumable agents may pass a stable
`id=` across successive `with langperf.trajectory(...)` blocks; ingest
upserts by `trajectory.id`, so all emitted spans land in one
`Trajectory` row regardless of how many process segments the run spans.

Non-final segments of such a run pass `final=False` so they don't stamp
`langperf.completed` (see below); only the last segment's `__exit__`
records the run's final outcome. See `sdk/README.md` §"Durable
trajectories" for the canonical usage pattern.
```

- [ ] **Step 2: Verify no other references need updating**

Run: `grep -n 'langperf.trajectory.id' sdk/ATTRIBUTES.md`
Expected: only the two occurrences in the updated section.

- [ ] **Step 3: Commit**

```bash
git add sdk/ATTRIBUTES.md
git commit -m "docs(sdk): ATTRIBUTES.md — caller-settable trajectory.id"
```

---

## Task 4: SDK — version bump + CHANGELOG

**Files:**
- Modify: `sdk/langperf/__init__.py:22`
- Modify: `sdk/pyproject.toml:3`
- Modify: `sdk/CHANGELOG.md` (prepend new entry above `[0.3.0]`)

- [ ] **Step 1: Bump `__version__`**

Edit `sdk/langperf/__init__.py`, last line:

```python
__version__ = "0.4.0"
```

- [ ] **Step 2: Bump `pyproject.toml` version**

Edit `sdk/pyproject.toml`, line 3:

```toml
version = "0.4.0"
```

- [ ] **Step 3: Prepend CHANGELOG entry**

Edit `sdk/CHANGELOG.md`. Insert above the existing `## [0.3.0] — 2026-04-22` line:

```markdown
## [0.4.0] — 2026-04-23

### Added
- `langperf.trajectory(id=...)` — optional caller-provided UUID. When
  supplied, the SDK uses it verbatim instead of autogenerating, letting
  multiple process segments of a durable/resumable run share one
  `Trajectory` row on the backend. Invalid UUIDs raise `ValueError` at
  `__enter__`. See `sdk/README.md` §"Durable trajectories".
- `langperf.trajectory(final=...)` — defaults to `True` (prior
  behavior). Pass `final=False` on all non-last segments of a durable
  run so `langperf.completed` is only stamped when the run truly ends.

```

- [ ] **Step 4: Verify version parity**

Run: `grep -E '^(__version__|version) = "' sdk/langperf/__init__.py sdk/pyproject.toml`
Expected: both read `"0.4.0"`.

- [ ] **Step 5: Commit**

```bash
git add sdk/langperf/__init__.py sdk/pyproject.toml sdk/CHANGELOG.md
git commit -m "chore(sdk): bump to 0.4.0"
```

---

## Task 5: API — confidence tests for multi-segment ingest

**Files:**
- Create: `api/tests/test_otlp_resume.py`

**Context:** Per spec, ingest already handles multi-segment trajectories — these tests are confidence guards only, no API code changes expected.

- [ ] **Step 1: Write failing-if-wrong tests**

Create `api/tests/test_otlp_resume.py`:

```python
"""Multi-segment (durable/resumable) trajectories — ingest upserts into one Trajectory row.

The SDK's new `id=` + `final=` kwargs enable a single logical run to
emit spans from multiple processes. These tests confirm the ingest path
already handles that shape — no code changes expected, but regressions
here would silently break durable-agent users.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import Agent, Organization, Project, Span, Trajectory
from app.otlp.decoder import DecodedBundle, DecodedSpan
from app.otlp.ingest import ingest_bundles


def _ns(dt: datetime) -> int:
    return int(dt.timestamp() * 1_000_000_000)


def _make_root(
    *,
    trajectory_id: str,
    trace_id: str,
    span_id: str,
    started_at: datetime,
    duration_s: float = 1.0,
    completed: bool | None = None,
    status_tag: str | None = None,
) -> DecodedSpan:
    attrs: dict = {
        "langperf.node.kind": "trajectory",
        "langperf.trajectory.id": trajectory_id,
    }
    if completed is not None:
        attrs["langperf.completed"] = completed
    if status_tag is not None:
        attrs["langperf.status_tag"] = status_tag
    end_ns = _ns(started_at) + int(duration_s * 1_000_000_000)
    return DecodedSpan(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=None,
        name=f"segment-{span_id[:4]}",
        kind="INTERNAL",
        start_time_unix_nano=_ns(started_at),
        end_time_unix_nano=end_ns,
        attributes=attrs,
        events=[],
        status={"code": "UNSET", "message": ""},
        scope={"name": None, "version": None},
    )


async def _seed(session) -> tuple[Organization, Agent]:
    org = Organization(id=str(uuid.uuid4()), name="Acme", slug="acme")
    project = Project(id=str(uuid.uuid4()), org_id=org.id, name="Default", slug="default")
    agent = Agent(
        id=str(uuid.uuid4()),
        org_id=org.id,
        project_id=project.id,
        signature=f"sig-{uuid.uuid4()}",
        name=f"widget-{uuid.uuid4().hex[:8]}",
        language="python",
        token_prefix=f"lp_{uuid.uuid4().hex[:8]}",
        token_hash="x" * 60,
        created_at=datetime.now(timezone.utc),
    )
    session.add_all([org, project, agent])
    await session.commit()
    return org, agent


@pytest.mark.asyncio
async def test_three_segments_roll_up_to_one_trajectory_row(session):
    """Three process segments → one Trajectory row; window spans all three."""
    org, agent = await _seed(session)
    traj_id = str(uuid.uuid4())
    seg1_start = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)
    seg2_start = seg1_start + timedelta(hours=1)
    seg3_start = seg2_start + timedelta(hours=1)

    # Segment 1 — non-final, no `completed` attribute.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="a" * 32,
                    span_id="1" * 16,
                    started_at=seg1_start,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # Segment 2 — still non-final.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="b" * 32,  # different trace_id — different OTel trace
                    span_id="2" * 16,
                    started_at=seg2_start,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # After segment 2: Trajectory.completed must still be None.
    traj = await session.get(Trajectory, traj_id)
    assert traj is not None
    assert traj.completed is None

    # Segment 3 — final.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="c" * 32,
                    span_id="3" * 16,
                    started_at=seg3_start,
                    completed=True,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # Refresh — one row, window spans all three, completed=True.
    await session.refresh(traj)
    assert traj.completed is True

    # started_at pinned to earliest segment; ended_at to latest.
    # sqlite strips tzinfo on round-trip — compare in UTC.
    def to_utc(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    assert to_utc(traj.started_at) == seg1_start
    assert to_utc(traj.ended_at) == seg3_start + timedelta(seconds=1)

    # Three root spans share one trajectory_id.
    result = await session.execute(
        select(Span).where(Span.trajectory_id == traj_id)
    )
    spans = list(result.scalars().all())
    assert len(spans) == 3
    assert all(s.parent_span_id is None for s in spans)


@pytest.mark.asyncio
async def test_mark_during_resume_last_writer_wins(session):
    """Second segment's mark() overwrites the first's on the Trajectory row."""
    org, agent = await _seed(session)
    traj_id = str(uuid.uuid4())
    t0 = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)

    # Seg 1 marks "bad".
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="a" * 32,
                    span_id="1" * 16,
                    started_at=t0,
                    status_tag="bad",
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()
    traj = await session.get(Trajectory, traj_id)
    assert traj.status_tag == "bad"

    # Seg 2 marks "good".
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="b" * 32,
                    span_id="2" * 16,
                    started_at=t0 + timedelta(hours=1),
                    status_tag="good",
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()
    await session.refresh(traj)
    assert traj.status_tag == "good"


@pytest.mark.asyncio
async def test_out_of_order_segment_arrival_converges(session):
    """Later segment arrives before earlier one — window converges to correct span."""
    org, agent = await _seed(session)
    traj_id = str(uuid.uuid4())
    t0 = datetime(2026, 4, 20, 10, 0, tzinfo=timezone.utc)

    # Segment 2 arrives first.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="b" * 32,
                    span_id="2" * 16,
                    started_at=t0 + timedelta(hours=1),
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    # Segment 1 arrives late.
    await ingest_bundles(
        session,
        [{
            "resource": {"attrs": {"service.name": "widget"}},
            "spans": [
                _make_root(
                    trajectory_id=traj_id,
                    trace_id="a" * 32,
                    span_id="1" * 16,
                    started_at=t0,
                )
            ],
        }],
        org_id=org.id,
        agent=agent,
    )
    await session.commit()

    traj = await session.get(Trajectory, traj_id)
    def to_utc(dt):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    # started_at pulled back to segment 1.
    assert to_utc(traj.started_at) == t0
    # ended_at stays at segment 2's end.
    assert to_utc(traj.ended_at) == t0 + timedelta(hours=1, seconds=1)
```

- [ ] **Step 2: Run tests**

Run: `pytest api/tests/test_otlp_resume.py -v`
Expected: all 3 PASS. If any fail, ingest does *not* actually handle multi-segment as the spec claims — investigate before proceeding rather than changing the tests.

- [ ] **Step 3: Full API test suite still green**

Run: `cd api && pytest -q`
Expected: all API tests pass.

- [ ] **Step 4: Commit**

```bash
git add api/tests/test_otlp_resume.py
git commit -m "$(cat <<'EOF'
test(api): multi-segment trajectory ingest confidence tests

Confirms existing ingest upsert-by-trajectory.id path correctly rolls
up multiple process segments into one Trajectory row — no code changes,
just regression coverage for durable-agent users.
EOF
)"
```

---

## Task 6: Web — `fmtDurationHuman` helper

**Files:**
- Modify: `web/lib/format.ts`
- Create: `web/tests/unit/format-duration-human.test.ts`

- [ ] **Step 1: Write failing test**

Create `web/tests/unit/format-duration-human.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { fmtDurationHuman } from "@/lib/format";

describe("fmtDurationHuman", () => {
  it("sub-second → ms", () => {
    expect(fmtDurationHuman(250)).toBe("250ms");
  });

  it("sub-minute → seconds", () => {
    expect(fmtDurationHuman(1500)).toBe("2s");
    expect(fmtDurationHuman(45_000)).toBe("45s");
  });

  it("sub-hour → minutes", () => {
    expect(fmtDurationHuman(60_000)).toBe("1m");
    expect(fmtDurationHuman(30 * 60_000)).toBe("30m");
  });

  it("sub-day → hours", () => {
    expect(fmtDurationHuman(60 * 60_000)).toBe("1h");
    expect(fmtDurationHuman(5 * 60 * 60_000)).toBe("5h");
  });

  it("days", () => {
    expect(fmtDurationHuman(24 * 60 * 60_000)).toBe("1d");
    expect(fmtDurationHuman(3 * 24 * 60 * 60_000)).toBe("3d");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test:unit -- format-duration-human`
Expected: FAIL with "fmtDurationHuman is not exported".

- [ ] **Step 3: Add `fmtDurationHuman` to `web/lib/format.ts`**

Append to `web/lib/format.ts`:

```typescript
/**
 * Render a coarse, human-readable duration — picks the largest non-zero unit
 * (ms | s | m | h | d). Used for resumption-gap labels where "3600000ms"
 * or "3600s" would obscure the shape of the pause.
 */
export function fmtDurationHuman(ms: number): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))}ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  return `${d}d`;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test:unit -- format-duration-human`
Expected: PASS.

- [ ] **Step 5: Typecheck**

Run: `cd web && npm run typecheck`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add web/lib/format.ts web/tests/unit/format-duration-human.test.ts
git commit -m "feat(web): add fmtDurationHuman helper for coarse durations"
```

---

## Task 7: Web — `buildSegments` helper

**Files:**
- Create: `web/lib/segments.ts`
- Create: `web/tests/unit/segments.test.ts`

- [ ] **Step 1: Write failing test**

Create `web/tests/unit/segments.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import type { Span } from "@/lib/api";
import { buildSegments } from "@/lib/segments";

function makeSpan(overrides: Partial<Span> = {}): Span {
  return {
    span_id: "s1",
    trace_id: "t1",
    trajectory_id: "tr1",
    parent_span_id: null,
    name: "test",
    kind: null,
    started_at: "2026-01-01T00:00:00.000Z",
    ended_at: "2026-01-01T00:00:01.000Z",
    duration_ms: 1000,
    attributes: {},
    events: null,
    status_code: null,
    notes: null,
    ...overrides,
  };
}

describe("buildSegments", () => {
  it("returns [] for no spans", () => {
    expect(buildSegments([])).toEqual([]);
  });

  it("returns one segment for a single-root trajectory", () => {
    const root = makeSpan({
      span_id: "r",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const segs = buildSegments([root]);
    expect(segs).toHaveLength(1);
    expect(segs[0].root.span_id).toBe("r");
    expect(segs[0].gapBeforeMs).toBe(0);
  });

  it("identifies multiple kind=trajectory roots as distinct segments", () => {
    const r1 = makeSpan({
      span_id: "r1",
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:05.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const r2 = makeSpan({
      span_id: "r2",
      started_at: "2026-01-01T00:10:00.000Z",
      ended_at: "2026-01-01T00:10:02.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const segs = buildSegments([r2, r1]); // out of order
    expect(segs.map((s) => s.root.span_id)).toEqual(["r1", "r2"]);
    // Gap is 10:00:00 - 00:00:05 = 9m55s → 595_000 ms.
    expect(segs[1].gapBeforeMs).toBe(595_000);
    expect(segs[0].gapBeforeMs).toBe(0);
  });

  it("ignores non-trajectory-kind roots when computing segments", () => {
    // An orphan non-trajectory root should not be treated as a segment.
    const trajectoryRoot = makeSpan({
      span_id: "r",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const orphan = makeSpan({
      span_id: "o",
      parent_span_id: null,
      attributes: { "langperf.node.kind": "tool" },
    });
    const segs = buildSegments([trajectoryRoot, orphan]);
    expect(segs).toHaveLength(1);
    expect(segs[0].root.span_id).toBe("r");
  });

  it("sorts segments by started_at ascending", () => {
    const later = makeSpan({
      span_id: "b",
      started_at: "2026-01-01T01:00:00.000Z",
      ended_at: "2026-01-01T01:00:01.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const earlier = makeSpan({
      span_id: "a",
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:01.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const segs = buildSegments([later, earlier]);
    expect(segs.map((s) => s.root.span_id)).toEqual(["a", "b"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test:unit -- segments`
Expected: FAIL — `buildSegments` not found.

- [ ] **Step 3: Implement `buildSegments`**

Create `web/lib/segments.ts`:

```typescript
import type { Span } from "@/lib/api";

export type Segment = {
  /** The `kind=trajectory` root span for this segment. */
  root: Span;
  /** Ms from the prior segment's `ended_at` to this segment's `started_at`. 0 for the first segment. */
  gapBeforeMs: number;
};

/**
 * Split a trajectory's spans into ordered durable-run segments.
 *
 * A segment is a root span (parent_span_id null) stamped with
 * `langperf.node.kind = "trajectory"`. Multiple such roots sharing one
 * trajectory id happen when the caller passes a stable `id=` to
 * `langperf.trajectory(...)` across process boundaries.
 *
 * Non-trajectory-kind orphan roots (rare) are intentionally excluded
 * from segment detection so they don't produce spurious "resumed after"
 * dividers in the UI.
 */
export function buildSegments(spans: Span[]): Segment[] {
  const roots = spans.filter(
    (s) =>
      s.parent_span_id == null &&
      (s.attributes as Record<string, unknown> | null)?.["langperf.node.kind"] ===
        "trajectory",
  );
  const ordered = [...roots].sort(
    (a, b) =>
      new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
  );
  return ordered.map((root, i) => {
    if (i === 0) return { root, gapBeforeMs: 0 };
    const prev = ordered[i - 1];
    const prevEnd = prev.ended_at
      ? new Date(prev.ended_at).getTime()
      : new Date(prev.started_at).getTime() + (prev.duration_ms ?? 0);
    const curStart = new Date(root.started_at).getTime();
    return { root, gapBeforeMs: Math.max(0, curStart - prevEnd) };
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test:unit -- segments`
Expected: all 4 tests PASS.

- [ ] **Step 5: Typecheck**

Run: `cd web && npm run typecheck`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add web/lib/segments.ts web/tests/unit/segments.test.ts
git commit -m "feat(web): buildSegments helper for durable-trajectory roots"
```

---

## Task 8: Web — TrajectoryTree renders multi-segment dividers

**Files:**
- Modify: `web/components/trajectory-tree.tsx`
- Create: `web/tests/unit/trajectory-tree.test.tsx`

- [ ] **Step 1: Write failing rendering test**

Create `web/tests/unit/trajectory-tree.test.tsx`:

```typescript
import { describe, it, expect, afterEach } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Span } from "@/lib/api";
import { TrajectoryTree } from "@/components/trajectory-tree";
import { SelectionProvider } from "@/components/selection-context";

afterEach(() => cleanup());

function makeSpan(overrides: Partial<Span> = {}): Span {
  return {
    span_id: "s",
    trace_id: "t",
    trajectory_id: "tr",
    parent_span_id: null,
    name: "test",
    kind: null,
    started_at: "2026-01-01T00:00:00.000Z",
    ended_at: "2026-01-01T00:00:01.000Z",
    duration_ms: 1000,
    attributes: {},
    events: null,
    status_code: null,
    notes: null,
    ...overrides,
  };
}

function renderTree(spans: Span[]) {
  return render(
    <SelectionProvider>
      <TrajectoryTree spans={spans} />
    </SelectionProvider>,
  );
}

describe("TrajectoryTree", () => {
  it("renders a single-segment tree identically (regression guard: no divider)", () => {
    renderTree([
      makeSpan({
        span_id: "r",
        name: "only-root",
        attributes: { "langperf.node.kind": "trajectory" },
      }),
    ]);
    expect(screen.getByText("only-root")).toBeTruthy();
    expect(screen.queryByText(/resumed after/i)).toBeNull();
  });

  it("renders a multi-segment divider labeled with the gap", () => {
    const seg1 = makeSpan({
      span_id: "r1",
      name: "seg-1",
      started_at: "2026-01-01T00:00:00.000Z",
      ended_at: "2026-01-01T00:00:05.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    const seg2 = makeSpan({
      span_id: "r2",
      name: "seg-2",
      // 1 hour after seg-1 ended
      started_at: "2026-01-01T01:00:05.000Z",
      ended_at: "2026-01-01T01:00:06.000Z",
      attributes: { "langperf.node.kind": "trajectory" },
    });
    renderTree([seg1, seg2]);
    expect(screen.getByText("seg-1")).toBeTruthy();
    expect(screen.getByText("seg-2")).toBeTruthy();
    // Exactly one divider between the two segments.
    const dividers = screen.queryAllByText(/resumed after/i);
    expect(dividers).toHaveLength(1);
    expect(dividers[0].textContent).toContain("1h");
  });

  it("renders dividers between N segments (one less than segment count)", () => {
    const mkRoot = (idx: number, startIso: string, endIso: string) =>
      makeSpan({
        span_id: `r${idx}`,
        name: `seg-${idx}`,
        started_at: startIso,
        ended_at: endIso,
        attributes: { "langperf.node.kind": "trajectory" },
      });
    renderTree([
      mkRoot(1, "2026-01-01T00:00:00.000Z", "2026-01-01T00:00:05.000Z"),
      mkRoot(2, "2026-01-01T00:10:00.000Z", "2026-01-01T00:10:05.000Z"),
      mkRoot(3, "2026-01-01T00:20:00.000Z", "2026-01-01T00:20:05.000Z"),
    ]);
    expect(screen.queryAllByText(/resumed after/i)).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test:unit -- trajectory-tree`
Expected: the multi-segment tests FAIL (no dividers rendered today).

- [ ] **Step 3: Update `TrajectoryTree` to render segments with dividers**

Replace the contents of `web/components/trajectory-tree.tsx`:

```tsx
"use client";

import { useMemo, useState } from "react";
import type { Span } from "@/lib/api";
import { kindSwatch } from "@/lib/colors";
import { useSelection } from "@/components/selection-context";
import { fmtDuration, fmtDurationHuman, fmtTokens } from "@/lib/format";
import { buildSegments } from "@/lib/segments";
import { extractTotalTokens, kindOf } from "@/lib/span-fields";
import { buildTree, type TreeNode } from "@/lib/tree";

export function TrajectoryTree({ spans }: { spans: Span[] }) {
  const roots = useMemo(() => buildTree(spans), [spans]);
  const segments = useMemo(() => buildSegments(spans), [spans]);

  if (roots.length === 0) {
    return (
      <div className="text-sm font-mono">
        <div className="p-5 text-patina">No spans.</div>
      </div>
    );
  }

  // Fast path: zero or one durable segment → render the full tree as today.
  // No divider; single-root trajectories are unchanged visually.
  if (segments.length <= 1) {
    return (
      <div className="text-sm font-mono">
        {roots.map((r) => (
          <TreeRow key={r.span.span_id} node={r} />
        ))}
      </div>
    );
  }

  // Multi-segment durable trajectory: render each segment's subtree with
  // a divider labeled by the resumption gap. Any non-trajectory-kind
  // orphan roots render after all segments so they're not mistaken for
  // part of a segment.
  const segmentRootIds = new Set(segments.map((s) => s.root.span_id));
  const orphanRoots = roots.filter((r) => !segmentRootIds.has(r.span.span_id));

  return (
    <div className="text-sm font-mono">
      {segments.map((seg, i) => {
        const treeRoot = roots.find((r) => r.span.span_id === seg.root.span_id);
        if (!treeRoot) return null;
        return (
          <div key={seg.root.span_id}>
            {i > 0 ? (
              <div
                className="px-3 py-1.5 text-[10px] uppercase tracking-wider text-patina border-y border-[color:var(--border)]/70 bg-steel-mist/30"
                role="separator"
                aria-label={`resumed after ${fmtDurationHuman(seg.gapBeforeMs)}`}
              >
                — resumed after {fmtDurationHuman(seg.gapBeforeMs)} —
              </div>
            ) : null}
            <TreeRow node={treeRoot} />
          </div>
        );
      })}
      {orphanRoots.map((r) => (
        <TreeRow key={r.span.span_id} node={r} />
      ))}
    </div>
  );
}

function TreeRow({ node }: { node: TreeNode }) {
  const { selectedId, select } = useSelection();
  const [open, setOpen] = useState(true);
  const hasChildren = node.children.length > 0;
  const kind = kindOf(node.span);
  const swatch = kindSwatch(kind);
  const isSelected = node.span.span_id === selectedId;

  const totalTokens = extractTotalTokens(node.span);

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => select(node.span)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            select(node.span);
          }
        }}
        className={`group flex items-center gap-2 px-3 py-1.5 border-b border-[color:var(--border)]/50 cursor-pointer hover:bg-warm-fog/[0.04] transition-colors ${
          isSelected ? "bg-aether-teal/10 border-l-2 border-l-aether-teal" : ""
        }`}
        style={{ paddingLeft: `${node.depth * 16 + 12}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen(!open);
            }}
            aria-label={open ? "Collapse children" : "Expand children"}
            aria-expanded={open}
            className="w-4 h-4 flex items-center justify-center text-patina hover:text-warm-fog -ml-1 mr-1"
          >
            {open ? "▼" : "▶"}
          </button>
        ) : (
          <span className="w-4 h-4 inline-block" />
        )}
        <span
          className="text-[10px] uppercase tracking-wider w-16"
          style={{ color: swatch.fg }}
        >
          {kind}
        </span>
        <span className="flex-1 truncate text-warm-fog">{node.span.name}</span>
        {totalTokens != null ? (
          <span className="text-[10px] text-patina tabular-nums">
            {fmtTokens(totalTokens)}t
          </span>
        ) : null}
        <span className="text-[10px] text-patina tabular-nums w-12 text-right">
          {fmtDuration(node.span.duration_ms)}
        </span>
        {node.span.notes ? (
          <span
            className="text-[10px] text-aether-teal"
            title={node.span.notes}
            aria-label="has note"
          >
            ●
          </span>
        ) : null}
        {node.span.status_code === "ERROR" ? (
          <span className="text-[10px] text-warn">!</span>
        ) : null}
      </div>
      {open && hasChildren ? (
        <div>
          {node.children.map((c) => (
            <TreeRow key={c.span.span_id} node={c} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test:unit -- trajectory-tree`
Expected: all 3 tests PASS.

- [ ] **Step 5: Full web unit suite still green**

Run: `cd web && npm run test:unit`
Expected: all unit tests pass.

- [ ] **Step 6: Lint + typecheck**

Run: `cd web && npm run typecheck && npm run lint`
Expected: clean.

- [ ] **Step 7: Manual browser check**

Run: `cd web && npm run dev`
Open a trajectory detail page — verify single-segment trajectories look identical to before. (Multi-segment manual verification comes after Task 11 gives us a real multi-segment example.)

- [ ] **Step 8: Commit**

```bash
git add web/components/trajectory-tree.tsx web/tests/unit/trajectory-tree.test.tsx
git commit -m "$(cat <<'EOF'
feat(web): TrajectoryTree renders multi-segment durable runs

When a trajectory contains multiple kind=trajectory root spans (durable
resumption), render each segment's subtree separated by a divider
labeled with the resumption gap. Single-segment trajectories are
unchanged.
EOF
)"
```

---

## Task 9: Web — TrajectoryTimeline idle-gap bands

**Files:**
- Modify: `web/components/trajectory-timeline.tsx`

- [ ] **Step 1: Render dashed idle-gap bands between segments**

Edit `web/components/trajectory-timeline.tsx`. Import `buildSegments`:

```tsx
import { buildSegments } from "@/lib/segments";
```

In the `TrajectoryTimeline` function, after the existing `useMemo` that computes `rows / trajectoryStartMs / totalMs` (around line 61), add a derivation of gap bands:

```tsx
  // Durable-run resumption gaps — dashed bands on the axis track that
  // make long pauses between segments visually obvious.
  const gapBands = useMemo(() => {
    const segs = buildSegments(spans);
    if (segs.length < 2) return [] as Array<{ offsetMs: number; widthMs: number }>;
    const toMs = (iso: string) => new Date(iso).getTime();
    const allStart = Math.min(...spans.map((s) => toMs(s.started_at)));
    const bands: Array<{ offsetMs: number; widthMs: number }> = [];
    for (let i = 1; i < segs.length; i++) {
      const prev = segs[i - 1].root;
      const prevEnd = prev.ended_at
        ? toMs(prev.ended_at)
        : toMs(prev.started_at) + (prev.duration_ms ?? 0);
      const curStart = toMs(segs[i].root.started_at);
      const gap = curStart - prevEnd;
      // Threshold: only draw for gaps > 1s. Sub-second gaps between
      // segments are numerically multi-segment but visually trivial.
      if (gap > 1000) {
        bands.push({ offsetMs: prevEnd - allStart, widthMs: gap });
      }
    }
    return bands;
  }, [spans]);
```

Inside the track container (the div that also hosts the `ticks` map, around line 240-265), add a rendering pass for the gap bands after the ticks map — still inside the same `<div ref={trackAnchorRef} ...>`:

```tsx
            {gapBands.map((g, i) => {
              const leftPx = g.offsetMs * effectivePxPerMs;
              const widthPx = Math.max(2, g.widthMs * effectivePxPerMs);
              return (
                <div
                  key={`gap-${i}`}
                  className="absolute top-0 bottom-0 pointer-events-none"
                  style={{
                    left: leftPx,
                    width: widthPx,
                    background:
                      "repeating-linear-gradient(90deg, rgba(167,139,250,0.18) 0 6px, transparent 6px 12px)",
                  }}
                  aria-hidden="true"
                />
              );
            })}
```

Also render the bands inside the rows track so they span vertically through the body. After the existing `{rows.map(...)}` block (around line 270-280), add at the end of the outer rows container (same sibling level), a full-height gap-band overlay:

```tsx
        {/* Resumption gap bands — dashed overlay across the full body
            height so long pauses between segments are legible in the
            timeline body as well as the axis. */}
        {gapBands.length > 0 ? (
          <div
            className="absolute top-0 bottom-0 pointer-events-none"
            style={{ left: LABEL_WIDTH, width: trackWidth }}
          >
            {gapBands.map((g, i) => {
              const leftPx = g.offsetMs * effectivePxPerMs;
              const widthPx = Math.max(2, g.widthMs * effectivePxPerMs);
              return (
                <div
                  key={`body-gap-${i}`}
                  className="absolute top-0 bottom-0"
                  style={{
                    left: leftPx,
                    width: widthPx,
                    background:
                      "repeating-linear-gradient(90deg, rgba(167,139,250,0.10) 0 6px, transparent 6px 12px)",
                  }}
                  aria-hidden="true"
                />
              );
            })}
          </div>
        ) : null}
```

Place this new overlay inside the existing `<div ref={scrollRef} ...>` container, after the rows `<div style={{ minWidth: ...}}>{rows.map(...)}</div>` block and before the hover-line block. The overlay is `position: absolute` relative to the scrollRef parent.

- [ ] **Step 2: Lint + typecheck**

Run: `cd web && npm run typecheck && npm run lint`
Expected: clean.

- [ ] **Step 3: Full web unit suite still green**

Run: `cd web && npm run test:unit`
Expected: all unit tests pass (timeline has no direct unit test; this change is visual).

- [ ] **Step 4: Manual browser check**

Run: `cd web && npm run dev`
Open a single-segment trajectory — timeline must look identical to before (no bands).

- [ ] **Step 5: Commit**

```bash
git add web/components/trajectory-timeline.tsx
git commit -m "$(cat <<'EOF'
feat(web): TrajectoryTimeline dashed idle-gap bands between segments

Resumption gaps > 1s between durable-trajectory segments render as
dashed purple overlays on the axis and body, making long pauses
legible at a glance.
EOF
)"
```

---

## Task 10: SDK — docs section + runnable example

**Files:**
- Modify: `sdk/README.md`
- Create: `examples/durable_agent.py`

- [ ] **Step 1: Append "Durable trajectories" section to SDK README**

Open `sdk/README.md` and append (at the end of the file):

```markdown
## Durable trajectories

For agents whose execution spans multiple processes — e.g. Temporal
workflows, queue-backed jobs, async human-in-the-loop flows — you can
thread every process segment into a single trajectory by passing a
stable `id=` on each `with langperf.trajectory(...)` block. LangPerf
observes; your app owns durability (persist the `id` alongside the
workflow state).

### Pattern

```python
import langperf
import uuid

langperf.init()

# Your app persists run_id with its workflow state.
run_id = str(uuid.uuid4())

# Segment 1 — kickoff; process exits after this.
with langperf.trajectory("support_agent", id=run_id, final=False):
    emit_approval_request()  # posts to Slack; returns immediately

# ... minutes/hours/days later, webhook wakes a fresh process ...

# Segment 2 — resume; still not the end.
with langperf.trajectory("support_agent", id=run_id, final=False):
    process_approval()

# Final segment — stamps completion.
with langperf.trajectory("support_agent", id=run_id, final=True):
    emit_final_report()
# → one Trajectory row spans all three segments; `completed=True` is
#   stamped here.
```

### Rules

- `id` must be a UUID string. To map a non-UUID key (e.g. a Temporal
  workflow ID), hash it: `id=str(uuid.uuid5(NAMESPACE, workflow_id))`.
- Pass `final=False` on every non-last segment so `langperf.completed`
  isn't prematurely stamped. The last segment uses `final=True` (the
  default).
- If the process dies before any segment finalizes, the trajectory's
  `completed` stays NULL and the UI shows "unknown" — same as any
  abandoned run today.

See `examples/durable_agent.py` for a runnable queue-based example.

### When *not* to use `id=`

Chat turns and single-process autonomous runs should keep using the
default (no `id` kwarg) — the SDK autogenerates a fresh UUID per
`with` block. For chat, pass `session_id=` instead to tie multiple
turns together in the UI without merging their spans.
```

- [ ] **Step 2: Create runnable example**

Create `examples/durable_agent.py`:

```python
"""Durable trajectory across process boundaries — queue-based example.

Demonstrates a multi-segment trajectory for an agent that suspends
between steps. In a real app each segment would run in a different
process (webhook, worker, scheduled job); here we simulate by
sequentially entering three `with langperf.trajectory(...)` blocks
that share one stable run_id.

Run with:
    export LANGPERF_API_TOKEN=lp_...
    python examples/durable_agent.py
"""
from __future__ import annotations

import time
import uuid

import langperf


def step_one() -> None:
    """Imagine this fires in process A, then the process exits."""
    with langperf.node(kind="tool", name="collect_inputs"):
        time.sleep(0.05)
    with langperf.node(kind="llm", name="draft_plan"):
        time.sleep(0.05)


def step_two() -> None:
    """Imagine this fires in process B, waking on a webhook."""
    with langperf.node(kind="tool", name="await_human_ack"):
        time.sleep(0.05)
    with langperf.node(kind="llm", name="revise_plan"):
        time.sleep(0.05)


def step_three() -> None:
    """Imagine this fires in process C, the final step."""
    with langperf.node(kind="tool", name="execute"):
        time.sleep(0.05)
    with langperf.node(kind="llm", name="summarize"):
        time.sleep(0.05)


def main() -> None:
    langperf.init()

    # Your app persists this run_id with its workflow state.
    run_id = str(uuid.uuid4())
    print(f"run_id = {run_id}")

    # Segment 1 — kickoff. In a real app the process would exit here.
    with langperf.trajectory("durable_demo", id=run_id, final=False):
        step_one()

    # Simulated pause — in a real app, minutes/hours later.
    time.sleep(0.5)

    # Segment 2 — resume. Still not final.
    with langperf.trajectory("durable_demo", id=run_id, final=False):
        step_two()

    time.sleep(0.5)

    # Segment 3 — final. Stamps langperf.completed=True on the row.
    with langperf.trajectory("durable_demo", id=run_id, final=True):
        step_three()

    langperf.flush()
    print("Done. Check the LangPerf UI for trajectory", run_id)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify example syntax**

Run: `python -c "import ast; ast.parse(open('examples/durable_agent.py').read())"`
Expected: no output (valid syntax).

- [ ] **Step 4: Commit**

```bash
git add sdk/README.md examples/durable_agent.py
git commit -m "docs(sdk): durable trajectories README section + example"
```

---

## Task 11: Full-repo CI pass + PR

- [ ] **Step 1: Lint + tests across SDK and API**

Run: `ruff check sdk/ api/ && pytest sdk/tests -q && cd api && pytest -q`
Expected: clean on all.

- [ ] **Step 2: Web lint + typecheck + unit**

Run: `cd web && npm run lint && npm run typecheck && npm run test:unit`
Expected: clean on all.

- [ ] **Step 3: Open PR against main**

Create PR from the feature branch:

```bash
gh pr create --title "feat: durable trajectory resumption" --body "$(cat <<'EOF'
## Summary

- SDK: `langperf.trajectory(id=..., final=...)` enables durable/resumable agents to thread multiple process segments into one Trajectory row.
- Web: `TrajectoryTree` renders multi-segment durable runs with "— resumed after X —" dividers; `TrajectoryTimeline` overlays dashed bands across resumption gaps.
- Ingest: no code changes (already upserts by `trajectory.id`); added confidence tests in `api/tests/test_otlp_resume.py`.
- Docs: new "Durable trajectories" section in `sdk/README.md` + `examples/durable_agent.py`.
- SDK bumped to 0.4.0 with CHANGELOG entry.

Spec: `docs/superpowers/specs/2026-04-23-durable-trajectory-resumption-design.md`.

## Test plan

- [x] SDK unit tests green (`pytest sdk/tests -q`)
- [x] API tests green including new multi-segment test (`cd api && pytest -q`)
- [x] Web unit tests green (`cd web && npm run test:unit`)
- [x] Web lint + typecheck green
- [ ] Manual: open an existing single-segment trajectory — UI unchanged
- [ ] Manual: run `examples/durable_agent.py`, open its trajectory in the UI — see 3 segments with dividers and dashed idle-gap bands

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: Confirm CI green**

Run: `gh pr checks --watch`
Expected: all four CI jobs pass (ruff, pytest sqlite, pytest postgres, web lint/typecheck/vitest).

---

## Self-Review Notes

**Spec coverage:**
- `id` kwarg → Task 1 ✓
- `final` kwarg → Task 2 ✓
- `ATTRIBUTES.md` update → Task 3 ✓
- `CHANGELOG.md` + version bump → Task 4 ✓
- SDK tests → Tasks 1 & 2 ✓
- API confidence tests → Task 5 ✓
- `fmtDurationHuman` helper → Task 6 ✓
- `buildSegments` helper → Task 7 ✓
- `TrajectoryTree` multi-root rendering → Task 8 ✓
- `TrajectoryTimeline` idle-gap bands → Task 9 ✓
- Docs + example → Task 10 ✓
- Scope-excluded items (no-op): no schema migration, no `Segment` table, no orchestration machinery, no UI "resume" button, no header "{N} segments across {total}" badge — deliberately deferred to keep scope tight; the tree divider and timeline bands together convey segmentation adequately for v1 and the header badge can be added later without schema impact.

**Type consistency:**
- `Segment.gapBeforeMs` used in Tasks 7, 8, and 9 — consistent.
- `fmtDurationHuman(ms: number): string` signature used in Tasks 6 & 8 — consistent.
- `buildSegments(spans: Span[]): Segment[]` — consistent across tasks.

**Deliberate deferrals from the spec surfaced back:** the "{N} segments across {total_wallclock}" header badge is listed in the spec but omitted from this plan. It adds value once multi-segment trajectories are common, but the tree divider + timeline band make segmentation visible without it, and adding it later is additive (reads `buildSegments(spans).length`).
