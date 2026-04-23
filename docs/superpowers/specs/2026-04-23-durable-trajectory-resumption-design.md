# Durable Trajectory Resumption — Design

**Status:** Design spec. Approved shape, ready for implementation planning.
**Date:** 2026-04-23
**Scope:** Extend `langperf.trajectory(...)` to support caller-provided trajectory IDs reused across Python processes / time, so a single logical "run" can accumulate spans even when the app suspends, resumes, or restarts. LangPerf observes; the app owns durability.

> Companion context: `CLAUDE.md` (SDK maintenance, ingest contract), `sdk/ATTRIBUTES.md` (wire protocol).

---

## Why this, why now

LangPerf's current trajectory model assumes a bounded `with` block in one Python process. That covers the vast majority of agent shapes — single-input autonomous runs, chat turns, short jobs — but breaks for two legitimate patterns:

1. **Durable / resumable agents.** A workflow runs step 1, suspends (DB write, queue ack, Temporal activity return), resumes step 2 minutes to days later in a different process or pod.
2. **Async human-in-the-loop.** Agent emits a request for human approval via Slack/email; the Python process exits; a webhook wakes a fresh process that continues the run.

Today each suspension boundary forces a new trajectory — users lose the per-run graph, quantitative rollups (step count, tokens, duration), and qualitative context (marks, notes). The workaround of "one giant trajectory that stays open for days" fights the triage model and the UI.

LangPerf is explicitly **not** orchestrating durability. Temporal, custom job queues, and framework-level resumption already solve that. This spec closes the observability gap: if the app can persist a stable run ID, LangPerf can thread all segments of that run into one visible trajectory.

## Who this is for

- **Andrew (builder, dogfood user)** — needs this for his own multi-stage agent runs
- **Future LangPerf users running durable workflows** — Temporal, Inngest, Celery, custom queue-backed agents
- **Async HITL chat/agent applications** — where the process ends between user input and agent continuation

## Scope

### In scope

- New `id: str | None = None` kwarg on `langperf.trajectory(...)` — caller-provided UUID reused across resumptions
- New `final: bool = True` kwarg on `langperf.trajectory(...)` — only the final segment stamps `langperf.completed`
- `sdk/ATTRIBUTES.md` update documenting caller-provided `langperf.trajectory.id` and segment semantics
- `sdk/CHANGELOG.md` entry and semver-minor version bump
- SDK tests exercising caller-provided ID and `final` flag
- API ingest tests confirming multi-segment trajectories roll up correctly
- Web UI changes to render multi-root trajectories as stacked segment subtrees with idle-gap labels
- Documentation page: "Durable trajectories" pattern with Temporal and plain-Python examples

### Explicitly out of scope

- **Branched conversations / fork-and-rejoin.** Not this product.
- **Concurrent-write detection or locking.** If two processes genuinely emit under one run ID simultaneously, that's app-side misuse; ingest remains idempotent by `span_id` and tolerates it.
- **First-class `Segment` entity in the schema.** Segments are derived views over root-less spans per trajectory; no new table.
- **Resumption/orchestration machinery in the SDK.** LangPerf observes; the app persists the run ID and calls `langperf.trajectory(id=...)` on each resume.
- **"Active duration" metric** (sum of segment durations, excluding idle gaps). Wall-clock `ended_at - started_at` stays authoritative for v1.
- **UI-surfaced "resume here" affordance.** No button that continues a trajectory from the LangPerf UI; the app is the only writer.

---

## Architecture

### Data model — no schema changes

A trajectory is still one `Trajectory` row keyed by `id` (UUID). Spans belong to a trajectory via `Span.trajectory_id`. Nothing in the schema changes.

**Segments are derived, not stored.** A segment = a root span (`parent_span_id IS NULL`) stamped with `langperf.node.kind = "trajectory"`. A durable trajectory with N resumptions has N such root spans sharing the same `trajectory_id`. The ingest path already tolerates this; the UI learns to render it.

### SDK surface (`sdk/langperf/trajectory.py`)

```python
langperf.trajectory(
    name: str | None = None,
    *,
    id: str | None = None,        # NEW
    final: bool = True,           # NEW
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: Mapping[str, Any] | None = None,
)
```

Behavior:

- **`id`** — if provided, the SDK validates it as a UUID (`uuid.UUID(id)`) and uses it verbatim instead of generating `uuid4()`. The value flows through OTel baggage to every child span, and is stamped on the root span as `langperf.trajectory.id`. If callers want to map a non-UUID key (e.g. a Temporal workflow ID), the idiom is `id=str(uuid.uuid5(NAMESPACE, workflow_id))`. Invalid input raises `ValueError` — fail loud at `__enter__`, not silently downstream.
- **`final`** — if `True` (default), `__exit__` stamps `langperf.completed = (exc_type is None)` as today. If `False`, the attribute is not stamped; the trajectory row's `completed` column stays at its current value. Callers set `final=False` for every segment except the last of the run.
- **All other kwargs** unchanged. `user_id`, `session_id`, and `metadata` are re-stamped on every segment's root span — harmless because these are span attributes, not `Trajectory` row columns. UI consumers that need a single attribution value per trajectory should read from the first segment's root span. Pass identical values across segments (they don't change within a single durable run).

### Ingest — no code changes required

The ingest path already behaves correctly for multi-segment trajectories:

- `resolve_trajectory_id` (`api/app/otlp/grouping.py:33`) honors an explicit `langperf.trajectory.id` on the span — no change.
- `_upsert_trajectory_for_span` (`api/app/otlp/ingest.py:148`) does `ON CONFLICT DO NOTHING` on `Trajectory.id`, then updates `started_at` / `ended_at` using `min` / `max` over arriving spans — so a segment arriving late naturally extends the window.
- `_apply_sdk_signals` (`api/app/otlp/ingest.py:235`) short-circuits on non-`kind=trajectory` spans and only writes fields when the attribute is present. Omitting `langperf.completed` from non-final segments means the column stays untouched until the final segment's span arrives.
- Spans are idempotent by `span_id` (unique); multiple trajectories with the same `trajectory.id` merging into one row is the existing behavior, not a new feature.

### UI — render multi-root trajectories as stacked segments

`web/components/trajectory-tree.tsx` and `trajectory-timeline.tsx` currently assume one root. Change them to accept an ordered list of roots:

- **Tree view:** Detect `roots.length > 1`. Render each root's subtree in its own vertical block, separated by a thin horizontal divider labeled *"— resumed after {duration_human(gap)} —"* where `gap = segment[i].started_at - segment[i-1].ended_at`. Keep the existing DAG layout within each segment.
- **Timeline view:** Show idle gaps as dashed empty bands so long pauses are visually obvious. Segments keep their existing span rows; the gap band is decorative.
- **Trajectory header / detail panel:** When multi-segment, show a small "{N} segments across {total_wallclock}" badge next to the duration. Single-segment trajectories render identically to today — no regression.

Detection is pure derivation: segments = `spans.filter(s => !s.parent_span_id && s.attributes["langperf.node.kind"] === "trajectory").sort(by started_at)`. Gaps = pairwise differences. No backend change.

### Contract updates

- `sdk/ATTRIBUTES.md` — document `langperf.trajectory.id` as caller-settable and stable across segments; document that multi-segment trajectories share one ID and emit N root spans.
- `sdk/CHANGELOG.md` — semver-minor entry. Callout: "Callers may now pass a stable `id` to `langperf.trajectory(...)` to accumulate spans across process boundaries; set `final=False` on all but the last segment."
- `sdk/langperf/__init__.py` + `sdk/pyproject.toml` — version bump (pair them, per `CLAUDE.md`).
- New `docs/` page or section: "Durable trajectories" pattern with a Temporal example and a plain-Python queue example.

### Canonical usage

```python
import langperf
import uuid

langperf.init()

# App persists this ID alongside its workflow state.
run_id = str(uuid.uuid4())

# Segment 1 — kickoff. App persists run_id + workflow state, then exits.
with langperf.trajectory("support_agent", id=run_id, final=False):
    emit_approval_request()  # posts to Slack/email, returns immediately

# ... minutes/hours/days later, webhook wakes a fresh process ...

# Segment 2 — resume. Not final; may hand off again.
with langperf.trajectory("support_agent", id=run_id, final=False):
    process_approval()

# Segment N — wrap up.
with langperf.trajectory("support_agent", id=run_id, final=True):
    emit_final_report()
# → one Trajectory row, completed=True stamped here, multi-root graph
```

### Chat pattern — unchanged

```python
# Each turn is its own trajectory. session_id ties them together.
with langperf.trajectory("chat_turn", session_id=conversation_id):
    ...
```

Chat users never touch `id=`. The default `uuid4()` path is unchanged.

---

## Edge cases and decisions

| Case | Behavior |
|---|---|
| Caller passes non-UUID `id` | `ValueError` at `__enter__` — fail loud. |
| Caller passes same `id` concurrently from two processes | Spans merge into one row (idempotent by `span_id`). No locking. If app truly needs serial execution, app owns that. |
| Every segment runs with `final=True` (user error) | Each segment's `langperf.completed` stamps the row; last writer wins. Harmless when every segment succeeds. If a mid-segment fails (`completed=False`) and a later segment succeeds, the row flips to `True` — incorrect. The `final=False` idiom on non-last segments exists specifically to prevent this; documented in the "Durable trajectories" docs page. |
| Trajectory never finalizes (process dies before `final=True` segment) | `Trajectory.completed` stays NULL → UI shows "unknown." Matches today's behavior for abandoned trajectories. |
| `mark()` called during a non-final segment | Targets the current segment's root span; `_apply_sdk_signals` writes `status_tag` / `notes` to the row. A later segment's `mark()` overwrites via the same path (last-writer-wins). This is the intended behavior — a run's status can legitimately evolve as it progresses. |
| First segment arrives after later segments (out-of-order ingest) | Ingest's `min(started_at)` / `max(ended_at)` logic handles reordering. Row converges to correct window regardless of arrival order. |
| Legacy trajectories (pre-change, single root) | Render identically. UI change is additive: `roots.length === 1` is the existing code path. |

---

## Testing

**SDK (`sdk/tests/test_trajectory_resume.py`):**
- Caller-provided UUID is used verbatim (baggage + span attribute).
- Non-UUID raises `ValueError`.
- `final=False` → `langperf.completed` not stamped on `__exit__`.
- `final=True` → `langperf.completed` stamped as today.
- Two sequential `with` blocks sharing an `id` emit two `kind=trajectory` root spans with identical `trajectory.id` attributes.

**API (`api/tests/test_otlp_resume.py`):**
- Ingest three segments across three separate OTLP requests for one `trajectory.id`.
- Assert: one Trajectory row; `started_at = segment_1.start`; `ended_at = segment_3.end`; `step_count` = sum across segments; `completed = True` after final segment; `completed` was NULL after segment 2.
- Mark-during-resume: `mark("bad")` on segment 2 sets `status_tag="bad"` on the row; a subsequent unmark on segment 3 overwrites.

**Web (`web/tests/unit/trajectory-tree.test.tsx`):**
- Multi-root input renders N segment subtrees with gap labels.
- Single-root input renders identically to pre-change output (regression guard).
- Timeline renders dashed idle-gap band between segments (threshold: any gap > 1s between one segment's `ended_at` and the next's `started_at`).

Playwright e2e deferred; unit coverage is sufficient for the rendering change.

---

## Migration and rollout

- **No DB migration.** Schema is unchanged.
- **No breaking SDK changes.** New kwargs are optional with non-behavioral defaults matching today (auto-generated UUID, `final=True`).
- **Version bump:** SDK minor (0.x.0 → 0.{x+1}.0). Per `CLAUDE.md`, pre-1.0 SDK tolerates surface additions in minor bumps.
- **Rollout order:** (1) SDK + tests merged and published, (2) API tests merged (no code change, just confidence), (3) UI multi-root rendering merged, (4) docs page. Order matters because users can start writing multi-segment code as soon as (1) ships even if (3) isn't there yet — the UI will render N disconnected subtrees without separators, which is ugly but not wrong.

---

## Open questions deferred

- **Should `Trajectory.duration_ms` exclude idle gaps?** Out of scope; wall-clock stays authoritative. Revisit if dogfood shows the wall-clock number misleads.
- **Should we add a `langperf.resume(id)` convenience API distinct from `trajectory(id=...)`?** No — the kwarg is self-documenting and avoids two idioms for one operation. Revisit only if users repeatedly ask.
- **Should heuristics (`api/app/heuristics/`) be aware of segmentation?** Currently they see the full span list regardless, which is probably correct — a loop spanning two segments is still a loop. No change needed, flag for future review if heuristics produce surprising results on multi-segment runs.
