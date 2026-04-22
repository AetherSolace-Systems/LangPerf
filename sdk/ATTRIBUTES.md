# LangPerf span-attribute contract

Public wire protocol between the `langperf` SDK and any ingesting
backend. Everything here is a plain OTel span attribute — no protobuf
extensions, no custom encoding. Consumers (including third-party OTel
tooling) can read the spans without depending on langperf code.

## Stability

- Attribute keys are **pre-1.0 stable** — we may add new ones in minor
  bumps but won't rename or remove existing ones without a major bump.
- Values follow OTel's attribute-value rules (scalar or homogeneous
  sequence). Non-scalar Python values passed through `metadata=` or
  `metric()` are coerced via `str()`.

Source of truth:

- SDK: `sdk/langperf/attributes.py`
- Backend mirror: `api/app/constants.py`

Change one, mirror to the other. A CI check could enforce this later; today
it's maintained by discipline + the SDK maintenance checklist in
`CLAUDE.md`.

## Trajectory identity (span-level)

Stamped on every span produced inside a `with langperf.trajectory(...)`
block. Baggage-propagated, so OpenInference-emitted spans inherit these
without explicit threading.

| Key | Type | Written by | Read by |
| --- | --- | --- | --- |
| `langperf.trajectory.id` | UUID string | `trajectory()` (baggage) | Ingest → `Trajectory.id` |
| `langperf.trajectory.name` | string | `trajectory(name=)` | Ingest → `Trajectory.name` |

## Node identity (span-level)

| Key | Type | Written by | Read by |
| --- | --- | --- | --- |
| `langperf.node.kind` | string | `trajectory()` (root=`"trajectory"`), `node(kind=)`, `tool` (=`"tool"`) | Ingest → `Span.kind`; also used to scope SDK-signal reads to the root span |
| `langperf.node.name` | string | `node(name=)`, `tool(name=)` | UI span label |

## SDK-side trajectory signals (root span only)

Emitted by `mark()` on the trajectory-root span. Backend reads them off
the `kind="trajectory"` span and copies them onto the `Trajectory` row.
Non-root spans carrying these keys are intentionally ignored.

| Key | Type | Written by | Read by |
| --- | --- | --- | --- |
| `langperf.status_tag` | enum string (`"good"`, `"bad"`, `"interesting"`, `"todo"`) | `mark(tag=)`, trajectory kwarg | Ingest → `Trajectory.status_tag` |
| `langperf.notes` | string | `mark(note=)` | Ingest → `Trajectory.notes` |
| `langperf.completed` | bool | trajectory context manager `__exit__` (auto) | Ingest → `Trajectory.completed` |
| `langperf.note` | string | legacy per-node note | UI span detail panel |

## User / session attribution (root span only)

Stamped on the trajectory root. Informational today; not yet first-class
on the `Trajectory` row (reserved for a future `trajectory.user_external_id`
column; do not rely on column writes for these).

| Key | Type | Written by |
| --- | --- | --- |
| `langperf.user.id` | string | `trajectory(user_id=)`, `set_user(user_id=)` |
| `langperf.user.email` | string | `set_user(email=)`, `Trajectory.set_user(email=)` |
| `langperf.user.display_name` | string | `set_user(display_name=)`, `Trajectory.set_user(display_name=)` |
| `langperf.session.id` | string | `trajectory(session_id=)`, `set_user(session_id=)` |

## Free-form metadata (any span)

| Key shape | Written by |
| --- | --- |
| `langperf.metadata.<user-key>` | `trajectory(metadata=)` (on root), `node(metadata=)` (on that node) |

`<user-key>` is whatever string the caller passed. Values that aren't
OTel scalars are coerced via `str()`.

## Custom metrics (any span)

| Key shape | Written by |
| --- | --- |
| `langperf.metric.<user-key>` | `metric(name, value)` (on current span) |

Heuristics may key off specific metric names in the future (e.g.
`langperf.metric.confidence`). Today they're informational; visible in
the span detail panel.

## Tool decorator capture (tool spans only)

Stamped on spans produced by `@langperf.tool`.

| Key | Type | Written by |
| --- | --- | --- |
| `langperf.tool.args` | JSON-encoded string (truncated at `max_payload_bytes`, default 16 KiB) | `tool()` before call |
| `langperf.tool.result` | JSON-encoded string (same truncation) | `tool()` after call |
| `langperf.tool.error` | `repr(exc)` | `tool()` on raised exception |

Truncated payloads end in `"…<truncated N bytes>"` — the string tells the
truth about what was captured.

## Resource attributes

Emitted once per process via `init()` and attached to every span's
resource.

| Key | Type | Written by |
| --- | --- | --- |
| `service.name` | string | `init(agent_name=)` — advisory / OTel interop only; the Agent bound to the bearer token is authoritative for display |
| `service.version` | string | `init(version=)` |
| `deployment.environment` | string | `init(environment=)` |
| `langperf.agent.signature` | hex string | auto (signature of caller) |
| `langperf.agent.language` | string (`"python"`) | auto |
| `langperf.agent.git_origin` | string | auto if inside a git repo |
| `langperf.agent.version.sha` | string | auto if inside a git repo |
| `langperf.agent.version.short_sha` | string | auto if inside a git repo |
| `langperf.agent.version.package` | string | auto from `pyproject.toml` / package metadata |
