# LangPerf — agent instructions

Working instructions for Claude / any agentic assistant driving work in
this repo. Human-facing docs live in `docs/` (roadmap, specs, plans);
this file is the quick-ref for getting useful work done.

## What this is

LangPerf is an OSS, self-hosted observability tool for LLM-based agents.
A Python SDK captures trajectories; a FastAPI + Next.js app ingests and
renders them. V1 shipped; V2 (collab + triage) shipped. Current state: in
dogfood, leaning into SDK breadth.

Full roadmap: `docs/ROADMAP.md` + `docs/superpowers/specs/2026-04-17-langperf-v2-dev-roadmap.md`.

## Repo layout

```
api/            FastAPI + async SQLAlchemy 2.0 + Alembic (Postgres prod, sqlite tests)
  app/          service modules, routes, ingest, heuristics
  tests/        pytest — run via `pytest` from api/
  alembic/      migrations; numbered 0001_.. onward, append-only
sdk/            Python SDK — standalone package, see "SDK maintenance" below
web/            Next.js 14 App Router + TypeScript + Tailwind (Aether Dusk tokens)
  app/          routes, server components
  components/   client components
  tests/        Playwright e2e; tests/unit is vitest
docs/
  ROADMAP.md    backlog of what's not in v1
  vision.md     full product vision
  superpowers/  specs + plans produced by the brainstorming/writing-plans skills
```

## Toolchain

- Python 3.12, lint: `ruff>=0.6,<0.7` (pinned in CI — see `.github/workflows/ci.yml`)
- Node 20, lint: eslint + prettier + tsc + vitest + playwright
- Alembic migrations are **append-only**. Never edit a merged migration;
  add a new numbered one. Migrations are frozen from ruff via per-file
  ignores.
- Tests: `pytest` in `api/`, `pytest` in `sdk/`, `npm test` in `web/`.

## Code conventions

- **Service layer.** API routes are thin adapters; SQL + permission logic
  lives in `api/app/services/*.py`. Extend a service; don't inline SQL in
  routes.
- **Comments.** Write WHY only. Hidden constraints, non-obvious
  invariants, subtle workarounds. Never narrate what the code does.
- **No scope creep.** A bug fix is a bug fix. Don't drive-by refactor.
- **No feature flags or back-compat shims** unless the task calls for it
  explicitly. Just change the code.
- **Error messaging.** Only validate at system boundaries (user input,
  external APIs). Trust internal code.

## CI

`.github/workflows/ci.yml` runs four jobs on every PR:

1. `ruff (api + sdk)` — ruff pinned to `>=0.6,<0.7`. Unpinned ruff
   drifts and flags clean code as dirty. Do not unpin.
2. `pytest (api) — sqlite` — default lane; fast.
3. `pytest (api) — postgres` — service-container lane; catches
   percentile_cont / FK / tz behavior sqlite masks.
4. `eslint + tsc + vitest (web)` — lint + typecheck + unit.

Playwright runs locally, not in CI yet.

## Triage model (context for agents that change UI or ingest)

Queue items come from three sources:

1. **Automated heuristics** (`api/app/heuristics/`). Five rules fire on
   every ingested trajectory: `tool_error`, `latency_outlier`,
   `apology_phrase`, `loop`, `low_confidence`. Hits land in
   `HeuristicHit`, sorted by severity.
2. **Manual tags** via UI — `good`/`bad`/`interesting`/`todo` → `Trajectory.status_tag`.
3. **SDK-side marks** — `langperf.mark("bad", note=...)` from code → stamped on
   the trajectory-root span → OTLP ingest reads it off and writes
   `Trajectory.status_tag` / `Trajectory.notes`. See `sdk/ATTRIBUTES.md`.

There is no user thumbs-up/down UI today.

---

## SDK maintenance

The `sdk/` directory is a standalone Python package (`langperf` on
PyPI-eventually). We expect to extract it to its own repo once it
stabilizes; keep the discipline today so extraction is mechanical.

### Hard rules

- **No imports from `api/`.** The SDK is a client; it must never depend
  on backend code. Attribute keys are duplicated between
  `sdk/langperf/attributes.py` and `api/app/constants.py` on purpose.
- **OTel-only dependencies.** SDK's install-time deps are
  `opentelemetry-*` and `openinference-*`. No ORM, no HTTP libs, no
  framework wrappers. New deps need a load-bearing reason; they ship to
  every user.
- **Public contract = `sdk/ATTRIBUTES.md`.** If you're adding or changing
  a `langperf.*` span attribute, update `ATTRIBUTES.md` and mirror the
  constant in `api/app/constants.py`. Don't rename existing keys pre-1.0.
- **Semver.** Pre-1.0 — add surface freely in minor bumps (`0.x.0`);
  breaking changes in minor bumps are tolerated but must land in
  `CHANGELOG.md` under "Breaking."
- **`py.typed` ships.** `sdk/langperf/py.typed` is listed in
  `tool.setuptools.package-data`; don't let it silently disappear.
- **Works standalone.** Every test in `sdk/tests/` must run without any
  backend present (we install an `InMemorySpanExporter`). If a test
  needs the server, it belongs in `api/tests/` instead.

### Everyday workflow

- Bump `__version__` in `sdk/langperf/__init__.py` and `version =` in
  `sdk/pyproject.toml` together. They drift otherwise.
- Add a `CHANGELOG.md` entry for any user-visible change — including
  bug fixes to attribute behavior, since users build on those keys.
- Run SDK tests from repo root: `pytest sdk/tests -q`.
- Check lint: `ruff check sdk/`. Ruff is pinned in `sdk/pyproject.toml`
  to match the api/ constraint.

### Backend bridging

The backend reads a subset of SDK-stamped attributes and writes them to
the `Trajectory` row. Currently:

- `langperf.status_tag` → `Trajectory.status_tag` (must be in `ALLOWED_TAGS`)
- `langperf.notes` → `Trajectory.notes`

These reads happen in `api/app/otlp/ingest.py::_apply_sdk_signals` and
only fire for the `kind="trajectory"` root span. Extending the bridge
means: add the key to `api/app/constants.py`, add a read in
`_apply_sdk_signals`, add an `api/tests/test_otlp_sdk_signals.py` case.

### Extraction-to-own-repo checklist

Before pulling `sdk/` into its own repo:

1. Run `grep -rE "from app\.|from api\." sdk/` — must return nothing.
2. Run `ruff check sdk/` + `pytest sdk/tests -q` — both green.
3. Copy `sdk/README.md`, `sdk/ATTRIBUTES.md`, `sdk/CHANGELOG.md`,
   `sdk/LICENSE` (if present) into the new repo alongside `langperf/`.
4. Keep a pointer from this repo (e.g. a git submodule during
   transition, or CI that installs the published wheel).
5. Preserve the attribute-mirror discipline: `api/app/constants.py`
   still lists the wire-protocol keys; CI should fail the api repo's
   build if the SDK's `ATTRIBUTES.md` contract diverges.

## Subagent / slice discipline

When running long refactors or feature work:

- Prefer small, named slices with explicit commits. `refactor(api): slice
  N — <scope>` is the established convention; don't lump unrelated
  changes.
- Subagents are fine for mechanical work; overkill for single-file
  edits. The earlier 16-slice QA push used subagents for disjoint file
  sets — that's the bar.
- Always open a PR branch; never push straight to `main`. PR → CI green
  → merge via `gh pr merge --merge --delete-branch`.

## Pointers

- `docs/superpowers/specs/2026-04-17-ui-shell-and-agent-first-class-design.md` — design rationale for the current UI shape.
- `docs/superpowers/specs/2026-04-19-graph-redesign.md` — trajectory graph design principles (flat, labelled edges, fullscreen).
- `api/app/heuristics/` — the five triage rules; each is a pure function over span dicts.
- `sdk/ATTRIBUTES.md` — wire-protocol source of truth.
