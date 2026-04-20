"""Pytest fixtures for the langperf SDK.

OpenTelemetry's global TracerProvider can only be set once per process —
subsequent ``set_tracer_provider()`` calls log a warning and are ignored.
So we set up a single session-scoped provider with a single
InMemorySpanExporter and reset the exporter between tests instead of
rebuilding the stack.

We also bypass ``langperf.init()`` entirely because it would install
OpenAI instrumentation (not needed here) and require
``LANGPERF_API_TOKEN`` (not needed here). Instead we stamp ``_state`` to
look initialized so calls like ``langperf.flush()`` work.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from opentelemetry import context as context_api, trace as trace_api
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from langperf import tracer as tracer_mod
from langperf._baggage import LangPerfBaggageSpanProcessor

# One provider + one exporter for the whole test session. Per-test
# isolation is achieved by clearing the exporter's buffer in the fixture
# teardown and dropping any leaked context at fixture setup.
_EXPORTER: InMemorySpanExporter = InMemorySpanExporter()
_PROVIDER: TracerProvider = TracerProvider()
_PROVIDER.add_span_processor(LangPerfBaggageSpanProcessor())
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace_api.set_tracer_provider(_PROVIDER)
tracer_mod._state.update(
    {"initialized": True, "provider": _PROVIDER, "identity": None}
)


@pytest.fixture
def exporter() -> Iterator[InMemorySpanExporter]:
    """Fresh view of the in-memory exporter for one test.

    Drops back to an empty OTel context on setup (so leaked baggage from
    a prior test doesn't pollute this one) and clears the exporter on
    teardown so the next test sees only its own spans.
    """
    reset_token = context_api.attach(context_api.Context())
    _EXPORTER.clear()
    try:
        yield _EXPORTER
    finally:
        _PROVIDER.force_flush()
        _EXPORTER.clear()
        context_api.detach(reset_token)


def finished_spans(exporter: InMemorySpanExporter) -> list:
    """Helper: return the finished spans (ordered by finish time)."""
    return list(exporter.get_finished_spans())
