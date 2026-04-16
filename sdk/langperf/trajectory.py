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
"""

from __future__ import annotations

import uuid
from typing import Optional

from opentelemetry import baggage, context as context_api, trace as trace_api

from langperf._baggage import BAGGAGE_TRAJECTORY_ID, BAGGAGE_TRAJECTORY_NAME


class _Trajectory:
    __slots__ = ("id", "name", "_ctx_token", "_span_cm", "_span")

    def __init__(self, name: Optional[str] = None):
        self.id: str = str(uuid.uuid4())
        self.name: Optional[str] = name
        self._ctx_token = None
        self._span_cm = None
        self._span = None

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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self._span_cm is not None:
                self._span_cm.__exit__(exc_type, exc_val, exc_tb)
        finally:
            if self._ctx_token is not None:
                context_api.detach(self._ctx_token)


def trajectory(name: Optional[str] = None) -> _Trajectory:
    """Open a trajectory scope.

    Usage:

        with langperf.trajectory("invoice query") as t:
            # All spans inside here are grouped under this trajectory.
            client.chat.completions.create(...)
            with langperf.node(kind="tool_call", name="search_invoices"):
                ...
    """
    return _Trajectory(name=name)
