"""Reusable span-builder helpers for synthesizing demo / test trajectories.

Extracted from `seed_demo_data.py` so other scripts (custom seed sets, unit
tests, integration repros) can build OpenInference-shaped spans without
copy-pasting the simulated-clock plumbing.

All time advancement is controlled by a module-level cursor; `fake_*` helpers
write spans with explicit `start_time` / `end_time` derived from that cursor
so durations are realistic without actually sleeping.

Typical usage::

    import langperf
    from scripts.demo_tracer import fake_trajectory, fake_llm, fake_tool

    langperf.init(agent_name="demo")
    with fake_trajectory("example"):
        fake_llm(system="...", user="...", response="...", duration_ms=200)
        fake_tool(name="search", args={"q": "x"}, result={"n": 3}, duration_ms=40)
    langperf.flush()
"""

from __future__ import annotations

import json
import random
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from opentelemetry import trace as trace_api
from opentelemetry.trace import Status, StatusCode, use_span

from langperf.attributes import (
    NODE_KIND,
    NODE_NAME,
    NOTE,
    TRAJECTORY_ID,
    TRAJECTORY_NAME,
)

# --------------------------------------------------------------------------- #
# Simulated clock                                                              #
# --------------------------------------------------------------------------- #

_NS_PER_MS = 1_000_000

# Start cursor 24 hours ago so trajectories spread across the last day.
_cursor_ns: int = int(time.time_ns()) - 24 * 60 * 60 * 1000 * _NS_PER_MS


def reset_clock(hours_ago: float = 24.0) -> None:
    """Reset the simulated cursor to `hours_ago` relative to now."""
    global _cursor_ns
    _cursor_ns = int(time.time_ns()) - int(hours_ago * 3600 * 1000 * _NS_PER_MS)


def _advance_ms(ms: float) -> int:
    global _cursor_ns
    _cursor_ns += int(ms * _NS_PER_MS)
    return _cursor_ns


def _jump_between_trajectories() -> None:
    """Jump forward 3-120 minutes between trajectories for realistic spacing."""
    _advance_ms(random.uniform(3 * 60 * 1000, 120 * 60 * 1000))


def parallel_branches(branches: list[Callable[[], None]]) -> None:
    """Run each branch as if concurrent: each starts at the same simulated time,
    and the cursor advances to the latest branch's end when all finish.

    Each entry in `branches` is a callable that emits spans. The shared cursor
    is rewound to the pre-block value before each branch runs, so they all have
    overlapping start times — the shape real parallel agent dispatch produces
    on a timeline.
    """
    global _cursor_ns
    start = _cursor_ns
    ends: list[int] = []
    for branch in branches:
        _cursor_ns = start
        branch()
        ends.append(_cursor_ns)
    _cursor_ns = max(ends) if ends else start


# --------------------------------------------------------------------------- #
# Span primitives                                                              #
# --------------------------------------------------------------------------- #

_tracer = None
_current_traj_id: str | None = None
_current_traj_name: str | None = None


def _tracer_obj():
    global _tracer
    if _tracer is None:
        _tracer = trace_api.get_tracer("langperf.demo_seed")
    return _tracer


def _stamp_trajectory(span) -> None:
    if _current_traj_id:
        span.set_attribute(TRAJECTORY_ID, _current_traj_id)
    if _current_traj_name:
        span.set_attribute(TRAJECTORY_NAME, _current_traj_name)


@contextmanager
def fake_trajectory(name: str, own_duration_ms: float = 5) -> Iterator[None]:
    """Open a trajectory root span with an explicit time range."""
    global _current_traj_id, _current_traj_name
    _jump_between_trajectories()
    _current_traj_id = str(uuid.uuid4())
    _current_traj_name = name
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    span.set_attribute(NODE_KIND, "trajectory")
    _stamp_trajectory(span)
    try:
        with use_span(span, end_on_exit=False):
            yield
    finally:
        _advance_ms(own_duration_ms)
        span.end(end_time=_cursor_ns)
        _current_traj_id = None
        _current_traj_name = None


@contextmanager
def fake_agent(
    name: str, description: str = "", own_duration_ms: float = 3
) -> Iterator[None]:
    """Open a nested agent scope. Children nest under it."""
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    span.set_attribute(NODE_KIND, "agent")
    span.set_attribute(NODE_NAME, name)
    if description:
        span.set_attribute(NOTE, description)
    _stamp_trajectory(span)
    try:
        with use_span(span, end_on_exit=False):
            yield
    finally:
        _advance_ms(own_duration_ms)
        span.end(end_time=_cursor_ns)


def fake_llm(
    *,
    name: str = "ChatCompletion",
    system: str,
    user: str,
    response: str = "",
    tool_calls: list[dict] | None = None,
    model: str = "gpt-4o",
    prompt_tok: int = 0,
    completion_tok: int = 0,
    duration_ms: float = 150,
    status: str = "OK",
) -> None:
    """Synthesize an OpenInference-style LLM span with explicit time range."""
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    try:
        _stamp_trajectory(span)
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("llm.system", "openai")
        span.set_attribute("llm.model_name", model)
        span.set_attribute(
            "llm.invocation_parameters",
            json.dumps({"model": model, "temperature": 0.7}),
        )

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        for i, m in enumerate(messages):
            span.set_attribute(f"llm.input_messages.{i}.message.role", m["role"])
            span.set_attribute(
                f"llm.input_messages.{i}.message.content", m["content"]
            )

        span.set_attribute("llm.output_messages.0.message.role", "assistant")
        if response:
            span.set_attribute("llm.output_messages.0.message.content", response)
        if tool_calls:
            for j, tc in enumerate(tool_calls):
                base = f"llm.output_messages.0.message.tool_calls.{j}.tool_call"
                span.set_attribute(f"{base}.function.name", tc["name"])
                span.set_attribute(
                    f"{base}.function.arguments", json.dumps(tc.get("args", {}))
                )
                if "id" in tc:
                    span.set_attribute(f"{base}.id", tc["id"])

        if prompt_tok:
            span.set_attribute("llm.token_count.prompt", prompt_tok)
        if completion_tok:
            span.set_attribute("llm.token_count.completion", completion_tok)
        if prompt_tok and completion_tok:
            span.set_attribute("llm.token_count.total", prompt_tok + completion_tok)

        span.set_attribute(
            "input.value", json.dumps({"messages": messages, "model": model})
        )
        span.set_attribute("input.mime_type", "application/json")

        output_content: dict[str, Any] = {"role": "assistant", "content": response or ""}
        if tool_calls:
            output_content["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{j}"),
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("args", {})),
                    },
                }
                for j, tc in enumerate(tool_calls)
            ]
        span.set_attribute(
            "output.value",
            json.dumps(
                {
                    "choices": [{"message": output_content}],
                    "model": model,
                    "usage": {
                        "prompt_tokens": prompt_tok,
                        "completion_tokens": completion_tok,
                        "total_tokens": prompt_tok + completion_tok,
                    },
                }
            ),
        )
        span.set_attribute("output.mime_type", "application/json")

        if status == "ERROR":
            span.set_status(Status(StatusCode.ERROR, "demo error"))
    finally:
        _advance_ms(duration_ms)
        span.end(end_time=_cursor_ns)


def fake_tool(
    *,
    name: str,
    args: Any,
    result: Any = None,
    description: str = "",
    duration_ms: float = 80,
    status: str = "OK",
) -> None:
    """Synthesize a tool_call span."""
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    try:
        _stamp_trajectory(span)
        span.set_attribute("openinference.span.kind", "TOOL")
        span.set_attribute(NODE_KIND, "tool_call")
        span.set_attribute(NODE_NAME, name)
        span.set_attribute("tool.name", name)
        if description:
            span.set_attribute("tool.description", description)
        args_str = args if isinstance(args, str) else json.dumps(args)
        span.set_attribute("input.value", args_str)
        span.set_attribute("input.mime_type", "application/json")
        if result is not None:
            result_str = result if isinstance(result, str) else json.dumps(result)
            span.set_attribute("output.value", result_str)
            span.set_attribute("output.mime_type", "application/json")
        if status == "ERROR":
            span.set_status(Status(StatusCode.ERROR, "demo error"))
    finally:
        _advance_ms(duration_ms)
        span.end(end_time=_cursor_ns)


def fake_reasoning(*, name: str, thought: str = "", duration_ms: float = 30) -> None:
    tracer = _tracer_obj()
    start = _cursor_ns
    span = tracer.start_span(name, start_time=start)
    try:
        _stamp_trajectory(span)
        span.set_attribute(NODE_KIND, "reasoning")
        span.set_attribute(NODE_NAME, name)
        if thought:
            span.set_attribute(NOTE, thought)
    finally:
        _advance_ms(duration_ms)
        span.end(end_time=_cursor_ns)
