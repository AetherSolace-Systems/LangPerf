# Agent-Centric Improvement Loop — Design

**Status:** Design spec. Approved shape, ready for implementation planning.
**Date:** 2026-04-22
**Scope:** V3 of LangPerf's improvement loop, delivered through the agent-detail page as the primary surface. Ships the minimum export surface (markdown agent profile + failure-mode CSV), adds end-user thumbs-down capture, and introduces a ranked agent-scoped worklist with data-heavy trend charts featuring a shared hover-cursor.

> Strategic companion: `docs/superpowers/specs/2026-04-17-langperf-v2-dev-roadmap.md`.
> V2 specs: `2026-04-17-v2a-auth-identity-foundation.md` … `2026-04-17-v2d-branched-rewrite-annotation.md`.

---

## Why this, why now

LangPerf captures, triages, and annotates agent trajectories. Today that data stops at the DB — there's no way to take the output of a review cycle and feed it back into the tools where engineers and SMEs actually work (Notion, Linear, training pipelines). That makes LangPerf a "roach motel": data in, nothing out.

V3 of the roadmap closes that loop. This spec scopes V3 specifically through an **agent-first** lens: LangPerf is an AI agent *performance* observation tool, so the agent is the natural unit of analysis and export. An engineer opens the agent's page and walks away with (a) a ranked list of what this agent needs next, and (b) exportable artifacts that feed external tools.

This spec deliberately resists the broader V3 surface named in the roadmap (JSONL training data, Slack/Linear/GitHub permalinks, direct fine-tuning integrations). Those come in a follow-on once this shape proves out in dogfood.

## Who this is for

- **Andrew (builder, dogfood user)** — opens the page to triage his own agent work
- **An optional pilot collaborator** — the spec doesn't require multi-user flow but doesn't preclude it; auth already exists from V2

---

## Scope

### In scope (V3, this spec)

- New SDK method `langperf.feedback(trajectory_id, thumbs, note?)` — thumbs-down capture from the end-user-facing app
- Auto-stamping `langperf.completed` on the SDK's trajectory context manager `__exit__`
- DB migration adding `trajectories.feedback_thumbs_down`, `feedback_thumbs_up`, `completed`
- Backend: `POST /v1/feedback` ingest route; `GET /api/agents/:name/{worklist,timeseries,profile.md,failures.csv}` endpoints
- Web: `TrendChart` + `SharedCursorProvider` + `AgentWorklist` + `ExportBar` components, wired into the agent detail overview tab
- Tests across all four layers (SDK, API, service, web unit + Playwright)

### Explicitly out of scope

- External-context node kinds (`db_query`, `file_read`, `file_write`, `http_request`) — cut because the user flagged this would bloat the graph's reading model. Thinking belongs on the LLM card; external side effects need a separate design if we ever revisit.
- SDK auto-instrumentation (SQLAlchemy, `open()`, `httpx`) — deferred
- JSONL preference-pair export from rewrites — V3-next
- Slack / Linear / GitHub permalink integrations — V3-next (CSV rows include `/t/:id` URLs as a partial substitute)
- Markdown summaries to Notion / Confluence as a push integration — V3-next (export stays pull-based)
- Direct fine-tuning integrations (Together, Fireworks, OpenAI-FT, HF TRL) — V4-bucket, not V3
- Cross-version regression analysis ("v3.2 got worse than v3.1 at X") — V4 along with replay
- Richer feedback capture (1–5 rating, free-text, categorization) — explicitly scoped down to minimal thumbs-only this phase

---

## Architecture

### Data-model changes — one append-only migration

Migration `0017_feedback_and_completion.py`:

```
trajectories
  + feedback_thumbs_down  int  not null default 0
  + feedback_thumbs_up    int  not null default 0
  + completed             bool nullable
```

`completed` is nullable so legacy rows stay "unknown" — they're excluded from the denominator of the completion-rate metric, neither helping nor hurting historical windows.

### SDK changes (langperf 0.3.0)

**`feedback(trajectory_id, thumbs, note=None)`** — fire-and-forget HTTP POST to `/v1/feedback`.

- Retry policy: 3 attempts, 0.25 / 0.5 / 1 s backoff, then silent drop.
- Never raises. Broken feedback must not break the calling app.
- Async runs in a background thread so the call returns immediately.

**Trajectory `__exit__` auto-stamp** — modify the trajectory context manager:

```python
with langperf.trajectory("name"):   # __enter__ as today
    ...
                                    # __exit__:
                                    #   completed = (exc_type is None)
                                    #   root_span.set_attribute(
                                    #       "langperf.completed", completed
                                    #   )
```

The backend reads this attribute in the OTLP ingest layer (`_apply_sdk_signals`, same place that reads `status_tag` / `notes`).

### Backend changes

**New routes:**

- `POST /v1/feedback` — feedback ingest. Same bearer-token auth pattern as `/v1/traces`. The token's agent must own the trajectory or 403.
- `GET /api/agents/:name/worklist?window=7d` — ranked list of issues for this agent, JSON
- `GET /api/agents/:name/timeseries?metrics=...&window=7d` — bucketed arrays for chart consumers, JSON
- `GET /api/agents/:name/profile.md` — streamed markdown profile
- `GET /api/agents/:name/failures.csv` — streamed CSV of flagged trajectories

**New services (`api/app/services/*`):**

- `agent_worklist.py` — scoring + ranking
- `agent_timeseries.py` — bucketing
- `agent_profile.py` — markdown rendering
- `agent_failures.py` — CSV rendering

**Ingest layer touchpoint:**

- `api/app/otlp/ingest.py::_apply_sdk_signals` — read `langperf.completed` and persist to `trajectories.completed`

**Constants mirror:**

- `api/app/constants.py` — add `TRAJECTORY_COMPLETED = "langperf.completed"` (paired with `sdk/langperf/attributes.py`, per the SDK-mirror discipline in `CLAUDE.md`)

### Web changes

New components in `web/components/`:
- `charts/trend-chart.tsx`
- `charts/shared-cursor.tsx`
- `agent/worklist.tsx`
- `agent/export-bar.tsx`

Modified: `web/app/agents/[name]/[tab]/page.tsx` — the Overview tab body gets replaced with the new layout (charts grid + worklist + export bar).

---

## Components

### Backend services

**`agent_worklist.py::compute(session, agent_id, window)` → `list[WorklistItem]`**

Sources pulled in parallel. "Last window" is the requested `window` ending now (e.g. `[now-7d, now]`). "Prior window" is the same-length window immediately before (e.g. `[now-14d, now-7d]`). Deltas compare these two halves.

1. `HeuristicHit` rows for this agent's trajectories in the last window, grouped by (kind, tool_name-if-applicable). One candidate per group. `last_seen_at` = max `HeuristicHit.created_at` in the group.
2. Cost delta = `mean(cost, last window) / mean(cost, prior window)` — **one aggregate candidate** if ≥ 1.25×. `last_seen_at` = `now`.
3. p95 latency delta — same shape on `p95(total_duration_ms)`. One aggregate candidate.
4. Thumbs-down counts from `feedback_thumbs_down` in the last window. One aggregate candidate when count ≥ 1. `last_seen_at` = max `Trajectory.updated_at` among trajectories with `feedback_thumbs_down > 0`.
5. Completion-rate drop = `(completed / non_null_total)_last − (completed / non_null_total)_prior`. One aggregate candidate if drop ≥ 5pp.
6. Per-tool success drop = `(ok / total)_last − (ok / total)_prior`, computed **per tool name**. **One candidate per tool** whose drop ≥ 5pp and `total_last ≥ 10` (min-sample floor to suppress noise from rarely-called tools).

Each candidate becomes a `WorklistItem{ signal, title, subtitle, affected_runs, last_seen_at, severity, score, urgency }`.

Return: top 20, ranked by `score`, ties broken by `last_seen_at` descending.

**`agent_timeseries.py::compute(session, agent_id, window, metrics)` → `list[MetricSeries]`**

Bucket step derived from window (24h → 5 min, 7d → 1 h, 30d → 6 h).

One SQL per metric family, not per metric:
- `duration_stats` → p50, p95, avg per bucket
- `cost_stats` → sum, count per bucket
- `tool_stats` → ok_count, total_count per bucket (scoped to tool-kind spans)
- `feedback_stats` → thumbs_down count (trajectory-level join) per bucket
- `completion_stats` → completed_count, non_null_total per bucket
- `token_stats` → sum(completion_tokens), sum(prompt_tokens) per bucket

Response:

```json
{
  "metric": "p95_latency",
  "window": "7d",
  "step_ms": 3600000,
  "buckets": [{"ts_ms": 1761196800000, "value": 1420.3, "count": 88}, ...]
}
```

**`agent_profile.py::render_markdown(session, agent_id, window)` → `str`**

Deterministic template. Sections:

1. Header — name, version, window
2. Snapshot — 4 KPIs with delta-vs-prior-window
3. Top issues — top 5 worklist items with severity + affected_runs
4. Tool landscape — table of top-N tools with call count, ok %, p95 ms
5. Recent patterns — failure-mode taxonomy counts

Golden-file testable. No template engine dep — f-strings and joins.

**`agent_failures.py::render_csv(session, agent_id, window)` → `Iterator[bytes]`**

Rows: trajectories where **any** of these is true within the window:
- any `HeuristicHit` exists for this trajectory
- `feedback_thumbs_down > 0`
- `status_tag in {'bad', 'todo'}`

Columns: `trajectory_id, started_at, heuristics, tools_errored, latency_ms, cost_usd, status_tag, feedback, notes, url`.

`url` = `${LANGPERF_WEB_BASE_URL}/t/${trajectory_id}` — clickable permalink so the CSV rows are actionable even without Slack/Linear push integrations.

### Web components

**`<TrendChart metric="..." buckets={...} format={...} color="..." height={160} />`**

- SVG-based, responsive to container width
- X axis: time ticks auto-chosen from bucket span
- Y axis: 4–5 labelled ticks
- Hover: compute `hoverX` in chart coords, call `SharedCursor.setX(hoverX)`
- Renders its own vertical-line cursor at `SharedCursor.x` and a pinned tooltip pill at top showing `format(value_at_bucket) · clock(ts)`

**`<SharedCursorProvider>{children}</SharedCursorProvider>`**

React context:

```ts
type Ctx = { hoverX: number | null; setX: (n: number | null) => void };
```

All `TrendChart`s inside the provider share state — one mouse move, 4 synchronized cursors + 4 value tooltips, each read from its own series. Mouseout anywhere sets `hoverX = null` and all cursors hide.

**`<AgentWorklist agent={...} items={...} />`**

Ranked rows: `rank · title · subtitle · urgency-pill · status-pill · arrow`.

Row click → navigate to `/history?agent=X&heuristic=Y` (or the nearest pre-filterable URL for that signal). Not all signals are heuristic-shaped — e.g. "cost delta" needs a different filter. Implementation plan picks which signals get a jump target and which are informational-only for this phase.

**`<ExportBar agent={...} />`**

Two `<a download>` anchors:
- `↓ profile.md` → `/api/agents/:name/profile.md`
- `↓ failures.csv` → `/api/agents/:name/failures.csv`

Server sets `Content-Disposition: attachment; filename="agent-<slug>-profile.md"`. Zero client state.

### Overview-tab integration

`web/app/agents/[name]/[tab]/page.tsx`, Overview branch:

```
<AppShell>
  <IdentityStrip agent={agent}>
    <ExportBar agent={agent} />   // top-right corner of the strip
  </IdentityStrip>

  <SharedCursorProvider>
    <div className="grid grid-cols-2 gap-4">
      <TrendChart metric="p95_latency"    ... />
      <TrendChart metric="cost_per_1k"    ... />
      <TrendChart metric="tool_success"   ... />
      <TrendChart metric="feedback_down"  ... />
    </div>
  </SharedCursorProvider>

  <AgentWorklist agent={agent} items={worklist} />
</AppShell>
```

A per-chart metric-picker dropdown (e.g., `[p95 latency ▾]` → swap in `completion_rate` / `token_efficiency` / `cost` / `tool_success`) gives access to the remaining quality metrics without forcing a 6-chart grid.

---

## Data flow

### Feedback write

```
app code → langperf.feedback(trajectory_id, thumbs="down")
  ↓  HTTP POST /v1/feedback  Authorization: Bearer lp_...
backend:
  → auth: bearer → Agent
  → load trajectory; 404 if missing
  → 403 if trajectory.agent_id != auth.agent_id
  → UPDATE trajectories SET feedback_thumbs_down = feedback_thumbs_down + 1 WHERE id = ?
  → if note: append to trajectories.notes
  → 204 No Content
```

### Completion stamping

SDK trajectory `__exit__` stamps the attribute on the root span. OTLP ingest picks it up in `_apply_sdk_signals` and persists to `trajectories.completed`. Legacy rows stay NULL and are excluded from completion-rate compute.

### Worklist compute (pull, on-demand per GET)

Called from the server component that renders the agent detail page. Not pre-computed — the signals are cheap to derive on the fly for a single agent over a 7d window.

### Scoring (one pure function)

```
score(item) = severity × log2(affected_runs + 1) × recency_decay(hours_since_last_seen)
recency_decay(h) = 2 ** (-h / 168)        # half-life of 1 week
urgency         = score ≥ 8 ? "high" : score ≥ 4 ? "med" : "low"
```

Severity constants:

| Signal source | Severity |
|---|---|
| `tool_error` heuristic | 3 |
| `loop` heuristic | 3 |
| thumbs-down counter | 3 |
| completion-rate drop ≥ 5pp | 3 |
| `latency_outlier` heuristic | 2 |
| `low_confidence` heuristic | 2 |
| cost delta ≥ 1.25× | 2 |
| p95 latency delta ≥ 1.25× | 2 |
| per-tool success drop ≥ 5pp | 2 |
| `apology_phrase` heuristic | 1 |

Ties: `last_seen_at DESC`.

### The 4 default charts

| Position | Chart | Metric | Source |
|---|---|---|---|
| top-left | p95 latency | p95 of `total_duration_ms` per bucket | `trajectories` |
| top-right | cost / 1k runs | `sum(cost_usd) / count() × 1000` per bucket | `trajectories` |
| bottom-left | tool success % | `ok / total` per bucket (span kind = tool) | `spans` |
| bottom-right | 👎 feedback | count of trajectories with `feedback_thumbs_down > 0` per bucket | `trajectories` |

All four receive the same `SharedCursorProvider`. Moving the mouse over any chart scrubs a violet cursor across all four, with each chart's tooltip pinned to its own value at that timestamp.

---

## Error handling

Boundary-only, per project convention in `CLAUDE.md`:

- **SDK `feedback()`**: network/4xx/5xx → retry up to 3× then silent drop. Never raises. Fire-and-forget is non-negotiable.
- **POST /v1/feedback**: 401 missing/invalid bearer, 404 trajectory missing, 403 cross-agent, 422 invalid body.
- **Worklist / timeseries / export endpoints**: agent missing → 404. Empty data → valid empty response (`[]`, empty `buckets`, markdown with "no data yet" notes, CSV header-only).
- **Trajectory `completed` attribute**: absent → treated as NULL (unknown), excluded from denominator. Never inferred.

---

## Testing

### Unit (pytest, sqlite lane)

- `test_worklist_scoring.py` — pure-function score/urgency tests with synthetic inputs
- `test_agent_profile_render.py` — golden-file fixture → expected markdown snapshot
- `test_agent_failures_csv.py` — golden-file fixture → expected CSV bytes
- `test_feedback_endpoint.py` — happy path increments, 403 cross-agent, 404 missing
- `test_completed_ingest.py` — OTLP span with the attribute persists `trajectories.completed`

### Integration (pytest, postgres service-container lane)

- `test_worklist_e2e.py` — ingested trajectories → GET worklist → expected ranking
- `test_timeseries_buckets.py` — `percentile_cont` behavior that sqlite can mask

### SDK (standalone, `InMemorySpanExporter` per SDK rule)

- `test_feedback_retry.py` — mock transport, 3 retries at 0.25/0.5/1s, no raise on final fail
- `test_trajectory_completed.py` — clean exit → attribute true; exception → attribute false

### Web (vitest)

- `shared-cursor.test.tsx` — two charts under one provider, pointer on A updates B's tooltip
- `trend-chart.test.tsx` — correct cursor positioning on sparse bucket array; tooltip honors `format` prop

### Playwright (not in CI lane today, but add specs)

- `agent-overview.spec.ts` — 4 charts render, hover shows 4 synchronized cursors + tooltips
- `agent-exports.spec.ts` — download buttons produce non-empty files with correct `Content-Disposition`
- `agent-worklist.spec.ts` — rows clickable, navigation filters trajectory list

### CI lane choice

- SDK tests remain zero-backend.
- Feedback endpoint tests run in both sqlite and postgres lanes (trivial to support).
- `percentile_cont` queries in timeseries live in the postgres lane only.

---

## Open questions for implementation planning

These are intentionally deferred to the implementation plan; the shape above doesn't depend on their resolution:

1. **Worklist row jump targets** — not every signal (cost delta, feedback cluster) has a matching pre-filterable page today. The plan decides which rows are clickable and which stay informational for this phase.
2. **Metric-picker dropdown placement** — does the per-chart `[p95 latency ▾]` dropdown live in the chart's top-left corner, a right-side menu, or the tab's filter bar? Plan picks one.
3. **Golden-file location for profile.md / failures.csv tests** — fixtures under `api/tests/fixtures/agent_profile/` vs. inline strings. Cosmetic; plan picks.

---

## Follow-on scope (post-V3-phase-1)

Named explicitly so they aren't forgotten:

- Richer feedback: 1–5 rating, free-text, categorization (`wrong_answer`, `incomplete`, `slow`, `unsafe`)
- JSONL training-data export from branched rewrites
- Slack / Linear / GitHub permalink push actions on worklist rows
- Markdown summary push to Notion / Confluence
- Cross-version regression ("v3.2 got worse at X") and replay-against-new-prompt (V4 — closes the engineer-facing side of the loop)
- Direct fine-tuning integrations (V4)
- SDK auto-instrumentation of DB / file / HTTP libraries
- External-context node kinds in the trajectory graph (if we ever revisit the "bloat vs. signal" tradeoff)

---

## References

- `docs/superpowers/specs/2026-04-17-langperf-v2-dev-roadmap.md` — strategic roadmap
- `docs/ROADMAP.md` — full v2+ backlog
- `docs/vision.md` — full product vision
- `docs/superpowers/specs/2026-04-17-ui-shell-and-agent-first-class-design.md` — agent-first UI shell
- `CLAUDE.md` — project conventions (service layer, append-only migrations, error handling at boundaries, SDK discipline)
- `sdk/ATTRIBUTES.md` — wire-protocol source of truth for span/trajectory attributes
