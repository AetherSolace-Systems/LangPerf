"""@langperf.tool — decorator sugar with args/result capture."""

from __future__ import annotations

import asyncio
import json

import pytest

import langperf
from langperf.attributes import NODE_KIND, NODE_NAME, TOOL_ARGS, TOOL_ERROR, TOOL_RESULT

from .conftest import finished_spans


def test_tool_bare_decorator_captures_args_and_result(exporter):
    @langperf.tool
    def add(a, b):
        return a + b

    with langperf.trajectory("outer"):
        assert add(2, 3) == 5

    span = next(s for s in finished_spans(exporter) if s.name == "add")
    assert span.attributes[NODE_KIND] == "tool"
    assert span.attributes[NODE_NAME] == "add"
    assert json.loads(span.attributes[TOOL_ARGS]) == {"a": 2, "b": 3}
    assert json.loads(span.attributes[TOOL_RESULT]) == 5


def test_tool_named_decorator(exporter):
    @langperf.tool("search-orders")
    def search(query: str, limit: int = 10):
        return [{"id": i} for i in range(limit)]

    with langperf.trajectory("outer"):
        search("laptops", limit=2)

    span = next(s for s in finished_spans(exporter) if s.name == "search-orders")
    assert json.loads(span.attributes[TOOL_ARGS]) == {"query": "laptops", "limit": 2}
    assert json.loads(span.attributes[TOOL_RESULT]) == [{"id": 0}, {"id": 1}]


def test_tool_capture_flags_honored(exporter):
    @langperf.tool("quiet", capture_args=False, capture_result=False)
    def q(x):
        return x

    with langperf.trajectory("outer"):
        q(42)

    span = next(s for s in finished_spans(exporter) if s.name == "quiet")
    assert TOOL_ARGS not in span.attributes
    assert TOOL_RESULT not in span.attributes


def test_tool_records_and_reraises_exception(exporter):
    @langperf.tool
    def boom():
        raise RuntimeError("nope")

    with langperf.trajectory("outer"):
        with pytest.raises(RuntimeError):
            boom()

    span = next(s for s in finished_spans(exporter) if s.name == "boom")
    assert "RuntimeError" in span.attributes[TOOL_ERROR]
    # OTel records the exception as a span event as well.
    event_names = [e.name for e in span.events]
    assert "exception" in event_names


def test_tool_truncates_oversized_payload(exporter):
    @langperf.tool("huge", max_payload_bytes=64)
    def huge():
        return "x" * 1024

    with langperf.trajectory("outer"):
        huge()

    span = next(s for s in finished_spans(exporter) if s.name == "huge")
    result = span.attributes[TOOL_RESULT]
    # Truncated + marker present.
    assert len(result.encode("utf-8")) < 200
    assert "truncated" in result


def test_tool_non_json_serializable_falls_back_to_repr(exporter):
    class Thing:
        def __repr__(self):
            return "<Thing>"

    @langperf.tool("thing")
    def get():
        return Thing()

    with langperf.trajectory("outer"):
        get()

    span = next(s for s in finished_spans(exporter) if s.name == "thing")
    # json.dumps default=repr serializes to "<Thing>" (JSON-encoded string).
    assert span.attributes[TOOL_RESULT] == '"<Thing>"'


def test_tool_async(exporter):
    @langperf.tool
    async def fetch(city):
        await asyncio.sleep(0)
        return {"city": city, "temp": 72}

    async def run():
        with langperf.trajectory("outer"):
            return await fetch("austin")

    result = asyncio.run(run())
    assert result == {"city": "austin", "temp": 72}

    span = next(s for s in finished_spans(exporter) if s.name == "fetch")
    assert json.loads(span.attributes[TOOL_ARGS]) == {"city": "austin"}
    assert json.loads(span.attributes[TOOL_RESULT]) == {"city": "austin", "temp": 72}
