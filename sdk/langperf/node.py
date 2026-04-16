"""`langperf.node(kind=..., name=...)` — works as both context manager and decorator.

    # context manager
    with langperf.node(kind="tool_call", name="search_invoices") as span:
        ...

    # decorator
    @langperf.node(kind="reasoning")
    def plan_next_step(state): ...

    # decorator without an explicit name — takes the function name
    @langperf.node(kind="tool_call")
    def search_invoices(range): ...
"""

from __future__ import annotations

import functools
from typing import Optional

from opentelemetry import trace as trace_api


class _Node:
    __slots__ = ("kind", "name", "_span_cm", "_span")

    def __init__(self, kind: str, name: Optional[str] = None):
        self.kind = kind
        self.name = name
        self._span_cm = None
        self._span = None

    # --- context-manager protocol ---
    def __enter__(self):
        tracer = trace_api.get_tracer("langperf")
        span_name = self.name or f"node.{self.kind}"
        self._span_cm = tracer.start_as_current_span(span_name)
        self._span = self._span_cm.__enter__()
        self._span.set_attribute("langperf.node.kind", self.kind)
        if self.name:
            self._span.set_attribute("langperf.node.name", self.name)
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span_cm is not None:
            return self._span_cm.__exit__(exc_type, exc_val, exc_tb)
        return None

    # --- decorator protocol ---
    def __call__(self, func):
        kind = self.kind
        name = self.name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with _Node(kind=kind, name=name):
                return func(*args, **kwargs)

        return wrapper


def node(*, kind: str, name: Optional[str] = None) -> _Node:
    """Return an object that can be used as a context manager OR a decorator."""
    return _Node(kind=kind, name=name)
