"""`@langperf.tool` — decorator sugar over `langperf.node(kind="tool")`
with automatic input/output capture.

    @langperf.tool()
    def search_orders(query: str, limit: int = 10) -> list[dict]:
        ...

    @langperf.tool("weather-lookup")
    async def fetch_weather(city: str) -> dict:
        ...

Both sync and async callables are supported. On each invocation:

  1. A new span is opened with ``kind="tool"`` and ``name="<function name>"``.
  2. If ``capture_args=True`` (default), the bound arguments are serialized
     to JSON and stamped as ``langperf.tool.args``. ``self`` is stripped.
  3. The function runs. If it raises, the exception is recorded on the
     span and re-raised.
  4. If ``capture_result=True`` (default), the return value is serialized
     to JSON and stamped as ``langperf.tool.result``.

Payloads are truncated to ``max_payload_bytes`` (default 16 KiB) to keep
spans from ballooning. The truncation is loud — the stamped string ends
in ``"…<truncated N bytes>"`` so the UI tells the truth about what was
captured.
"""

from __future__ import annotations

import functools
import inspect
import json
from collections.abc import Callable
from typing import Any, Optional, TypeVar, Union, overload

from langperf.attributes import TOOL_ARGS, TOOL_ERROR, TOOL_RESULT
from langperf.node import _Node

F = TypeVar("F", bound=Callable[..., Any])

_DEFAULT_MAX_PAYLOAD_BYTES = 16 * 1024


def _safe_dumps(obj: Any) -> str:
    """JSON-serialize arbitrary objects. Fall back to ``repr`` when things
    aren't JSON-friendly — the goal is to surface *something* in the UI."""
    try:
        return json.dumps(obj, default=repr, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(obj)


def _truncate(s: str, limit: int) -> str:
    if len(s.encode("utf-8")) <= limit:
        return s
    # Binary-truncate to `limit` bytes; UTF-8 safe via errors="ignore".
    head = s.encode("utf-8")[:limit].decode("utf-8", errors="ignore")
    return f"{head}…<truncated {len(s.encode('utf-8')) - len(head.encode('utf-8'))} bytes>"


def _capture_args(func: Callable[..., Any], args: tuple, kwargs: dict) -> Optional[str]:
    """Bind args+kwargs against the function signature and serialize to JSON.

    Strips ``self`` on bound methods. Returns None if binding fails (e.g.
    wrong arity) so we don't crash the user's tool on a serialization
    hiccup.
    """
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(*args, **kwargs)
        bound.apply_defaults()
        payload = {
            k: v for k, v in bound.arguments.items() if k not in ("self", "cls")
        }
    except (TypeError, ValueError):
        return None
    return _safe_dumps(payload)


@overload
def tool(name: Callable[..., Any], /) -> Callable[..., Any]: ...
@overload
def tool(
    name: Optional[str] = None,
    *,
    capture_args: bool = True,
    capture_result: bool = True,
    max_payload_bytes: int = _DEFAULT_MAX_PAYLOAD_BYTES,
) -> Callable[[F], F]: ...


def tool(
    name: Union[str, Callable[..., Any], None] = None,
    *,
    capture_args: bool = True,
    capture_result: bool = True,
    max_payload_bytes: int = _DEFAULT_MAX_PAYLOAD_BYTES,
) -> Any:
    """Decorator turning any function into a LangPerf ``kind=tool`` span.

    Supports bare ``@langperf.tool`` (no parens) and parameterized
    ``@langperf.tool("name", capture_result=False)`` forms.
    """
    # Bare decorator form: @langperf.tool
    if callable(name):
        return _build_wrapper(
            name,
            name=None,
            capture_args=capture_args,
            capture_result=capture_result,
            max_payload_bytes=max_payload_bytes,
        )

    def decorator(func: F) -> F:
        return _build_wrapper(
            func,
            name=name,
            capture_args=capture_args,
            capture_result=capture_result,
            max_payload_bytes=max_payload_bytes,
        )  # type: ignore[return-value]

    return decorator


def _build_wrapper(
    func: Callable[..., Any],
    *,
    name: Optional[str],
    capture_args: bool,
    capture_result: bool,
    max_payload_bytes: int,
) -> Callable[..., Any]:
    span_name = name or func.__name__

    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def awrapper(*args, **kwargs):
            with _Node(kind="tool", name=span_name) as span:
                if capture_args:
                    if (payload := _capture_args(func, args, kwargs)) is not None:
                        span.set_attribute(
                            TOOL_ARGS, _truncate(payload, max_payload_bytes)
                        )
                try:
                    result = await func(*args, **kwargs)
                except Exception as exc:
                    span.set_attribute(TOOL_ERROR, repr(exc))
                    raise
                if capture_result:
                    span.set_attribute(
                        TOOL_RESULT,
                        _truncate(_safe_dumps(result), max_payload_bytes),
                    )
                return result

        return awrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _Node(kind="tool", name=span_name) as span:
            if capture_args:
                if (payload := _capture_args(func, args, kwargs)) is not None:
                    span.set_attribute(
                        TOOL_ARGS, _truncate(payload, max_payload_bytes)
                    )
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                span.set_attribute(TOOL_ERROR, repr(exc))
                raise
            if capture_result:
                span.set_attribute(
                    TOOL_RESULT,
                    _truncate(_safe_dumps(result), max_payload_bytes),
                )
            return result

    return wrapper


__all__ = ["tool"]
