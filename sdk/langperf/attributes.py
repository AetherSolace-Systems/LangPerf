"""LangPerf span-attribute keys — public contract.

Canonical strings the SDK stamps on every span. The backend, tests, and
third-party consumers reach for these constants instead of hardcoding
`"langperf.*"`.

Deliberately duplicated in `api/app/constants.py`. Both sides speak OTel
over the wire; neither takes a code dependency on the other. Change either
file and mirror the change in the other — the SDK README and
`sdk/ATTRIBUTES.md` describe what's stable.
"""

# ── Trajectory identity (stamped on every span in a `with trajectory()`) ─
TRAJECTORY_ID = "langperf.trajectory.id"
TRAJECTORY_NAME = "langperf.trajectory.name"

# ── Node kind + name (stamped on node spans) ─────────────────────────────
NODE_KIND = "langperf.node.kind"
NODE_NAME = "langperf.node.name"

# ── SDK-supplied signals that bridge to backend columns ──────────────────
# Read by the OTLP ingest layer off the `kind=trajectory` root span and
# copied into `Trajectory.status_tag` / `Trajectory.notes` so UI filters
# reflect SDK-side marks.
STATUS_TAG = "langperf.status_tag"
NOTES = "langperf.notes"
NOTE = "langperf.note"  # legacy — per-node note; kept for back-compat

# ── User / session attribution (per-trajectory) ──────────────────────────
USER_ID = "langperf.user.id"
USER_EMAIL = "langperf.user.email"
USER_DISPLAY_NAME = "langperf.user.display_name"
SESSION_ID = "langperf.session.id"

# ── Free-form metadata and metric prefixes ───────────────────────────────
# Users pass `metadata={"feature_flag": "A"}` → stamped as
# `langperf.metadata.feature_flag = "A"`. Similarly for `metric(...)`.
METADATA_PREFIX = "langperf.metadata."
METRIC_PREFIX = "langperf.metric."

# ── Tool decorator capture ───────────────────────────────────────────────
TOOL_ARGS = "langperf.tool.args"
TOOL_RESULT = "langperf.tool.result"
TOOL_ERROR = "langperf.tool.error"

# ── Allowed values for STATUS_TAG (mirror of api/app/constants.ALLOWED_TAGS) ─
ALLOWED_TAGS: frozenset[str] = frozenset({"good", "bad", "interesting", "todo"})

__all__ = [
    "TRAJECTORY_ID",
    "TRAJECTORY_NAME",
    "NODE_KIND",
    "NODE_NAME",
    "STATUS_TAG",
    "NOTES",
    "NOTE",
    "USER_ID",
    "USER_EMAIL",
    "USER_DISPLAY_NAME",
    "SESSION_ID",
    "METADATA_PREFIX",
    "METRIC_PREFIX",
    "TOOL_ARGS",
    "TOOL_RESULT",
    "TOOL_ERROR",
    "ALLOWED_TAGS",
]
