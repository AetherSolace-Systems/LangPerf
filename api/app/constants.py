"""Shared constants — attribute keys, allowed enum values.

Attribute keys are canonical strings stamped on OTel spans by the LangPerf
SDK (see `sdk/langperf/_baggage.py`). We duplicate them here rather than
importing from the SDK because the backend is designed to run against any
OTLP source — not only traces produced by the LangPerf SDK — so a hard
import dependency on the SDK would be the wrong direction.
"""

from __future__ import annotations

from datetime import timedelta

ALLOWED_TAGS: frozenset[str] = frozenset(
    {"good", "bad", "interesting", "todo"}
)

# ── Rolling-window deltas for dashboard / metrics endpoints ──────────────
WINDOW_DELTAS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

# ── Default failure-mode seeds (slug, label, color) ──────────────────────
# Duplicated verbatim in alembic migration 0010 — migrations are frozen,
# so the literal there stays; this is the source of truth for runtime code.
DEFAULT_FAILURE_MODES: list[tuple[str, str, str]] = [
    ("wrong_tool", "Wrong tool", "warn"),
    ("bad_args", "Bad args", "warn"),
    ("hallucination", "Hallucination", "peach-neon"),
    ("loop", "Loop", "peach-neon"),
    ("misunderstood_intent", "Misunderstood intent", "steel-mist"),
]

# ── Span-attribute keys the LangPerf SDK stamps ──────────────────────────
# Kept in sync with sdk/langperf/attributes.py. Wire protocol — change
# either file and mirror the change on the other side.
ATTR_TRAJECTORY_ID = "langperf.trajectory.id"
ATTR_TRAJECTORY_NAME = "langperf.trajectory.name"
ATTR_NODE_KIND = "langperf.node.kind"
ATTR_NODE_NAME = "langperf.node.name"

# Bridge: SDK mark() populates these on the trajectory-kind root span; the
# OTLP ingest layer copies them onto the Trajectory row so UI filters
# reflect SDK-side marks.
ATTR_STATUS_TAG = "langperf.status_tag"
ATTR_NOTES = "langperf.notes"
ATTR_COMPLETED = "langperf.completed"

# User attribution — informational; not yet first-class on the trajectory row.
ATTR_USER_ID = "langperf.user.id"
ATTR_USER_EMAIL = "langperf.user.email"
ATTR_USER_DISPLAY_NAME = "langperf.user.display_name"
ATTR_SESSION_ID = "langperf.session.id"

# ── OTel resource-attribute keys ─────────────────────────────────────────
ATTR_SERVICE_NAME = "service.name"
ATTR_DEPLOYMENT_ENVIRONMENT = "deployment.environment"

# ── Agent identity — OTel resource attributes emitted by the SDK ─────────
ATTR_AGENT_SIGNATURE = "langperf.agent.signature"
ATTR_AGENT_VERSION_SHA = "langperf.agent.version.sha"
ATTR_AGENT_VERSION_SHORT_SHA = "langperf.agent.version.short_sha"
ATTR_AGENT_VERSION_PACKAGE = "langperf.agent.version.package"
ATTR_AGENT_LANGUAGE = "langperf.agent.language"
ATTR_AGENT_GIT_ORIGIN = "langperf.agent.git_origin"
