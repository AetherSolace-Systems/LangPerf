"""`langperf.trajectory(name=...)` — scopes a group of spans as one trajectory.

Implementation:
  1. Generate a UUID for this trajectory.
  2. Set it (and optionally a human name) as OTel baggage, so every span created
     inside the `with` block sees it in its parent context. The
     LangPerfBaggageSpanProcessor (registered at init time) reads the baggage
     on `on_start` and stamps attributes on every span — including ones created
     by OpenInference instrumentation.
  3. Open a root span to wrap the block — gives the trajectory a well-defined
     start/end and makes the tree have a single visible root.
  4. Stash the root span in a contextvar so `mark()` / `metric()` / `set_user()`
     can target the trajectory from anywhere inside the block.
"""

from __future__ import annotations

import contextvars
import uuid
from collections.abc import Mapping
from typing import Any, Optional

from opentelemetry import baggage, context as context_api, trace as trace_api
from opentelemetry.sdk.trace import Span

from langperf._baggage import BAGGAGE_TRAJECTORY_ID, BAGGAGE_TRAJECTORY_NAME
from langperf.attributes import (
    COMPLETED,
    METADATA_PREFIX,
    SESSION_ID,
    USER_DISPLAY_NAME,
    USER_EMAIL,
    USER_ID,
)

# Visible to sibling modules (marks.py, tool.py) so they can target the
# trajectory root span. None when we're outside a trajectory scope.
_TRAJECTORY_SPAN: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar(
    "langperf_trajectory_span", default=None
)
_TRAJECTORY_ID: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "langperf_trajectory_id", default=None
)


class _Trajectory:
    __slots__ = (
        "id",
        "name",
        "user_id",
        "session_id",
        "metadata",
        "_ctx_token",
        "_span_cm",
        "_span",
        "_traj_span_token",
        "_traj_id_token",
    )

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

    def __enter__(self) -> "_Trajectory":
        # 1. Set baggage so all child spans inherit the trajectory id/name.
        ctx = baggage.set_baggage(BAGGAGE_TRAJECTORY_ID, self.id)
        if self.name:
            ctx = baggage.set_baggage(BAGGAGE_TRAJECTORY_NAME, self.name, context=ctx)
        self._ctx_token = context_api.attach(ctx)

        # 2. Open a root span covering the trajectory.
        tracer = trace_api.get_tracer("langperf")
        span_name = self.name or "trajectory"
        self._span_cm = tracer.start_as_current_span(span_name)
        self._span = self._span_cm.__enter__()
        self._span.set_attribute("langperf.node.kind", "trajectory")
        self._span.set_attribute(BAGGAGE_TRAJECTORY_ID, self.id)
        if self.name:
            self._span.set_attribute(BAGGAGE_TRAJECTORY_NAME, self.name)

        # 3. Per-trajectory attribution — stamped once on the root span.
        if self.user_id is not None:
            self._span.set_attribute(USER_ID, self.user_id)
        if self.session_id is not None:
            self._span.set_attribute(SESSION_ID, self.session_id)
        if self.metadata:
            _stamp_metadata(self._span, self.metadata)

        # 4. Bind to contextvars so marks.py / tool.py can reach the root span.
        self._traj_span_token = _TRAJECTORY_SPAN.set(self._span)
        self._traj_id_token = _TRAJECTORY_ID.set(self.id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            # Stamp completion BEFORE closing the span context. Otherwise
            # the span is already ended and the attribute silently drops.
            if self._span is not None:
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

    def set_user(
        self,
        user_id: str,
        *,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> None:
        """Attach user attribution to this trajectory after __enter__."""
        if self._span is None:
            return
        self._span.set_attribute(USER_ID, user_id)
        if email is not None:
            self._span.set_attribute(USER_EMAIL, email)
        if display_name is not None:
            self._span.set_attribute(USER_DISPLAY_NAME, display_name)


def trajectory(
    name: Optional[str] = None,
    *,
    id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> _Trajectory:
    """Open a trajectory scope.

    Usage:

        with langperf.trajectory("invoice query") as t:
            # All spans inside here are grouped under this trajectory.
            client.chat.completions.create(...)
            with langperf.node(kind="tool", name="search_invoices"):
                ...

    Parameters:
        name: Human-readable label shown in the UI.
        id: Caller-provided UUID for this trajectory. Threading the same
            id through multiple `with` blocks (across processes, retries,
            or workflow replays) groups all resulting spans under a
            single `Trajectory` row. Must be UUID-parseable; defaults to
            an autogenerated UUID4.
        user_id: External user identifier (your auth subject). Emits
            `langperf.user.id` on the root span.
        session_id: External session identifier (chat/session token).
            Emits `langperf.session.id` on the root span.
        metadata: Free-form key/value pairs. Each `(k, v)` is emitted as
            `langperf.metadata.<k> = v` on the root span. Values must be
            OTel-compatible scalars (str/int/float/bool) or sequences of
            them — complex types are coerced via str().
    """
    return _Trajectory(
        name=name,
        id=id,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata,
    )


def _stamp_metadata(span: Span, metadata: Mapping[str, Any]) -> None:
    """Emit each metadata entry as `langperf.metadata.<key> = value`.

    OTel only accepts scalars and homogeneous sequences as attribute
    values. Non-scalar values get coerced via str() rather than dropped so
    the user sees *something* in the UI.
    """
    for key, value in metadata.items():
        attr_key = f"{METADATA_PREFIX}{key}"
        if isinstance(value, str | bool | int | float):
            span.set_attribute(attr_key, value)
        else:
            span.set_attribute(attr_key, str(value))
