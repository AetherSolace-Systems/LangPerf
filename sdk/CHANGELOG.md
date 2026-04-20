# Changelog

All notable changes to the `langperf` SDK. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Semver: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html).

## [0.2.1] — 2026-04-20

### Changed
- `agent_name=` / `LANGPERF_AGENT_NAME` is now explicitly advisory.
  The bearer token alone identifies the Agent; the backend uses the
  Agent's registered name for `trajectory.service_name` regardless of
  what the SDK sends. Callers no longer need to keep the SDK name in
  sync with the UI. Docs updated to drop `agent_name=` from the
  recommended `init()` call.

### Fixed
- Backend ingest now overwrites `Trajectory.service_name` with the
  token-authorized `Agent.name` if the user renames the agent in the
  UI after initial ingest.

## [0.2.0] — 2026-04-20

### Added
- `mark(tag=, note=)` — tag the active trajectory as
  `good`/`bad`/`interesting`/`todo` and/or attach a note from code. Bridges
  to the UI's tag filter column via the OTLP ingest layer.
- `metric(name, value)` — stamp a scalar metric on the current span
  (`langperf.metric.<name>`).
- `set_user(user_id, email?, display_name?, session_id?)` — attach user
  attribution to the active trajectory after `__enter__`.
- `current_trajectory_id()` — returns the active trajectory UUID for
  deep-linking from external logs.
- `@langperf.tool` decorator — sugar over `@node(kind="tool")` with
  automatic JSON capture of args + return value (truncated at 16 KiB by
  default; configurable via `max_payload_bytes=`). Records exceptions.
  Supports both sync and async callables.
- `trajectory()` accepts `user_id=`, `session_id=`, `metadata=` kwargs.
- `node()` accepts `metadata=` kwarg.
- `py.typed` marker — enables inline type hints for mypy/pyright
  downstream.
- `ATTRIBUTES.md` — formal span-attribute contract, pre-1.0 stable.

### Changed
- `node()` decorator now detects `async def` targets and wraps them
  correctly.

### Fixed
- Ingest layer (backend) now reads `langperf.status_tag` / `langperf.notes`
  off the trajectory-root span and writes them to the `Trajectory` row.
- Ingest layer datetime comparisons now tolerate sqlite's naive-datetime
  round-trip behavior (affected test environments only; production
  Postgres was unaffected).

## [0.1.0] — earlier

Initial release.

- `init(...)` with auto-installed OpenAI (OpenInference) instrumentation.
- `trajectory(name=)` context manager.
- `node(kind=, name=)` context manager + decorator.
- `flush()` — force batch exporter flush.
- OTel resource attributes for agent identity (signature, git SHA,
  package version, language).
- Per-agent `LANGPERF_API_TOKEN` bearer auth.
