"""`langperf.node(kind=..., name=...)` — works as both context manager and decorator.

    # context manager
    with langperf.node(kind="tool", name="search_invoices") as span:
        ...

    # decorator
    @langperf.node(kind="reasoning")
    def plan_next_step(state): ...

    # decorator without an explicit name — takes the function name
    @langperf.node(kind="tool")
    def search_invoices(range): ...
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Mapping
from typing import Any, Optional

from opentelemetry import trace as trace_api
from opentelemetry.sdk.trace import Span

from langperf.attributes import METADATA_PREFIX, NODE_KIND, NODE_NAME


class _Node:
    __slots__ = ("kind", "name", "metadata", "_span_cm", "_span")

    def __init__(
        self,
        kind: str,
        name: Optional[str] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ):
        self.kind = kind
        self.name = name
        self.metadata = dict(metadata) if metadata else None
        self._span_cm = None
        self._span = None

    # --- context-manager protocol ---
    def __enter__(self) -> Span:
        tracer = trace_api.get_tracer("langperf")
        span_name = self.name or f"node.{self.kind}"
        self._span_cm = tracer.start_as_current_span(span_name)
        self._span = self._span_cm.__enter__()
        self._span.set_attribute(NODE_KIND, self.kind)
        if self.name:
            self._span.set_attribute(NODE_NAME, self.name)
        if self.metadata:
            for k, v in self.metadata.items():
                attr_key = f"{METADATA_PREFIX}{k}"
                if isinstance(v, str | bool | int | float):
                    self._span.set_attribute(attr_key, v)
                else:
                    self._span.set_attribute(attr_key, str(v))
        return self._span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span_cm is not None:
            return self._span_cm.__exit__(exc_type, exc_val, exc_tb)
        return None

    # --- decorator protocol ---
    def __call__(self, func):
        kind = self.kind
        name = self.name or func.__name__
        metadata = self.metadata

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def awrapper(*args, **kwargs):
                with _Node(kind=kind, name=name, metadata=metadata):
                    return await func(*args, **kwargs)

            return awrapper

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with _Node(kind=kind, name=name, metadata=metadata):
                return func(*args, **kwargs)

        return wrapper


def node(
    *,
    kind: str,
    name: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> _Node:
    """Return an object that can be used as a context manager OR a decorator.

    Parameters:
        kind: Free-form span classification — common values are "tool",
            "llm", "reasoning", "retrieval". The UI treats these specially;
            anything else renders as a generic node.
        name: Display name. If omitted when used as a decorator, the
            wrapped function's name is used.
        metadata: Per-node free-form key/value pairs. Each `(k, v)` is
            emitted as `langperf.metadata.<k> = v` on the span.
    """
    return _Node(kind=kind, name=name, metadata=metadata)
