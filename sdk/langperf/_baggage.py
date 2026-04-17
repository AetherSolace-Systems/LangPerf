"""Custom SpanProcessor that stamps LangPerf baggage onto every span.

The `langperf.trajectory(...)` context manager sets baggage keys for the
trajectory id and name. This processor runs on every span start and copies
those baggage values onto the span as attributes — which means auto-generated
spans from OpenInference (or any other OTel instrumentation) inherit the
trajectory context automatically, without the user having to thread it through.
"""

from __future__ import annotations

from typing import Optional

from opentelemetry import baggage, context as context_api
from opentelemetry.context.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor

from langperf.attributes import TRAJECTORY_ID, TRAJECTORY_NAME

# Baggage keys reuse the attribute names — baggage name == final span attribute.
BAGGAGE_TRAJECTORY_ID = TRAJECTORY_ID
BAGGAGE_TRAJECTORY_NAME = TRAJECTORY_NAME

ATTR_TRAJECTORY_ID = TRAJECTORY_ID
ATTR_TRAJECTORY_NAME = TRAJECTORY_NAME


class LangPerfBaggageSpanProcessor(SpanProcessor):
    def on_start(
        self, span: Span, parent_context: Optional[Context] = None
    ) -> None:
        ctx = parent_context if parent_context is not None else context_api.get_current()
        traj_id = baggage.get_baggage(BAGGAGE_TRAJECTORY_ID, context=ctx)
        if traj_id is not None:
            span.set_attribute(ATTR_TRAJECTORY_ID, str(traj_id))
        traj_name = baggage.get_baggage(BAGGAGE_TRAJECTORY_NAME, context=ctx)
        if traj_name is not None:
            span.set_attribute(ATTR_TRAJECTORY_NAME, str(traj_name))

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return True
