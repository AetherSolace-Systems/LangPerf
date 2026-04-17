"""Shared constants — attribute keys, allowed enum values.

Attribute keys are canonical strings stamped on OTel spans by the LangPerf
SDK (see `sdk/langperf/_baggage.py`). We duplicate them here rather than
importing from the SDK because the backend is designed to run against any
OTLP source — not only traces produced by the LangPerf SDK — so a hard
import dependency on the SDK would be the wrong direction.
"""

from __future__ import annotations

ALLOWED_TAGS: frozenset[str] = frozenset(
    {"good", "bad", "interesting", "todo"}
)

# ── Span-attribute keys the LangPerf SDK stamps ──────────────────────────
# Kept in sync with sdk/langperf/_baggage.py (ATTR_TRAJECTORY_*).
ATTR_TRAJECTORY_ID = "langperf.trajectory.id"
ATTR_TRAJECTORY_NAME = "langperf.trajectory.name"
ATTR_NODE_KIND = "langperf.node.kind"
ATTR_NODE_NAME = "langperf.node.name"

# ── OTel resource-attribute keys ─────────────────────────────────────────
ATTR_SERVICE_NAME = "service.name"
ATTR_DEPLOYMENT_ENVIRONMENT = "deployment.environment"
