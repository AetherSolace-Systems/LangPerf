"""SDK-side signals that travel up to the backend as span attributes.

`mark()`, `metric()`, `set_user()`, and `current_trajectory_id()` all read
the trajectory-root span off the contextvar populated by
`langperf.trajectory()`. Outside of a trajectory block they no-op with a
single warning — surfacing a hard error would defeat the "drop-in, safe by
default" posture the SDK aims for.

Every signal here is visible in the UI via the span's attribute panel.
Some are also read by the OTLP ingest layer and copied onto the
Trajectory row:

  - `langperf.status_tag` → `Trajectory.status_tag` (tag filter column)
  - `langperf.notes`      → `Trajectory.notes`      (notes field)

See `sdk/ATTRIBUTES.md` for the full public attribute contract.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from langperf.attributes import (
    ALLOWED_TAGS,
    METRIC_PREFIX,
    NOTES,
    SESSION_ID,
    STATUS_TAG,
    USER_DISPLAY_NAME,
    USER_EMAIL,
    USER_ID,
)
from langperf.trajectory import _TRAJECTORY_ID, _TRAJECTORY_SPAN

logger = logging.getLogger("langperf")


def mark(tag: Optional[str] = None, *, note: Optional[str] = None) -> None:
    """Mark the active trajectory with a status tag and/or a note.

    Both are stamped on the trajectory-root span and, on ingest, copied
    onto the Trajectory row so UI filters (`good` / `bad` / `interesting`
    / `todo`) and notes reflect the SDK-side signal.

    Example::

        with langperf.trajectory("order lookup"):
            result = agent.run(...)
            if "I apologize" in result:
                langperf.mark("bad", note="refusal response")

    Parameters:
        tag: One of ``"good"``, ``"bad"``, ``"interesting"``, ``"todo"``.
            Unknown values are still emitted (for future taxonomy
            extensions) but a warning is logged.
        note: Free-form note text. Overwrites any previous note.

    Silently no-ops if called outside a `langperf.trajectory()` block.
    """
    if tag is None and note is None:
        return

    span = _TRAJECTORY_SPAN.get()
    if span is None:
        logger.warning(
            "langperf.mark() called outside a trajectory — signal dropped"
        )
        return

    if tag is not None:
        if tag not in ALLOWED_TAGS:
            logger.warning(
                "langperf.mark(tag=%r): not in the canonical set %s; "
                "still emitted but UI filters may ignore it",
                tag,
                sorted(ALLOWED_TAGS),
            )
        span.set_attribute(STATUS_TAG, tag)

    if note is not None:
        span.set_attribute(NOTES, note)


def metric(name: str, value: Any) -> None:
    """Record a numeric or scalar metric on the current span.

    Emitted as ``langperf.metric.<name> = <value>`` on the innermost span
    (i.e. the node you're inside of, or the trajectory root if you're not
    inside a node). Triage heuristics can read these to score
    trajectories.

    Example::

        with langperf.node(kind="llm", name="classifier"):
            prediction, confidence = model(...)
            langperf.metric("confidence", confidence)

    Parameters:
        name: Short metric identifier (dotted is fine: ``"latency.p95"``).
        value: Scalar OTel-compatible value — str, bool, int, float, or
            a homogeneous sequence thereof. Non-scalars are coerced via
            ``str()`` rather than dropped.
    """
    from opentelemetry import trace as trace_api

    span = trace_api.get_current_span()
    if span is None or not span.is_recording():
        logger.warning("langperf.metric(%r) called outside a span — dropped", name)
        return

    attr_key = f"{METRIC_PREFIX}{name}"
    if isinstance(value, str | bool | int | float):
        span.set_attribute(attr_key, value)
    else:
        span.set_attribute(attr_key, str(value))


def set_user(
    user_id: str,
    *,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Attach user attribution to the active trajectory.

    Equivalent to passing ``user_id=`` to ``trajectory()`` — use when you
    don't know the user until after the block has started (e.g. auth
    happens inside the agent run).

    Silently no-ops if called outside a trajectory.
    """
    span = _TRAJECTORY_SPAN.get()
    if span is None:
        logger.warning("langperf.set_user() called outside a trajectory")
        return
    span.set_attribute(USER_ID, user_id)
    if email is not None:
        span.set_attribute(USER_EMAIL, email)
    if display_name is not None:
        span.set_attribute(USER_DISPLAY_NAME, display_name)
    if session_id is not None:
        span.set_attribute(SESSION_ID, session_id)


def current_trajectory_id() -> Optional[str]:
    """Return the UUID of the active trajectory, or None if not inside one.

    Useful for building deep links back to the LangPerf UI from your own
    app — e.g. attaching ``/t/<id>`` to a Sentry event or log line.
    """
    return _TRAJECTORY_ID.get()


__all__ = [
    "mark",
    "metric",
    "set_user",
    "current_trajectory_id",
]
