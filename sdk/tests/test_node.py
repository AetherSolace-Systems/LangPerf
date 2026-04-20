"""node() context manager + decorator, sync + async."""

from __future__ import annotations

import asyncio

import langperf
from langperf.attributes import METADATA_PREFIX, NODE_KIND, NODE_NAME

from .conftest import finished_spans


def test_node_context_manager(exporter):
    with langperf.trajectory("outer"):
        with langperf.node(kind="reasoning", name="think"):
            pass

    spans = {s.name: s for s in finished_spans(exporter)}
    assert spans["think"].attributes[NODE_KIND] == "reasoning"
    assert spans["think"].attributes[NODE_NAME] == "think"


def test_node_decorator_uses_function_name(exporter):
    @langperf.node(kind="tool")
    def lookup(x):
        return x + 1

    with langperf.trajectory("outer"):
        assert lookup(2) == 3

    spans = {s.name: s for s in finished_spans(exporter)}
    assert "lookup" in spans
    assert spans["lookup"].attributes[NODE_KIND] == "tool"


def test_node_metadata_kwargs(exporter):
    with langperf.trajectory("outer"):
        with langperf.node(kind="llm", name="gen", metadata={"model": "gpt-oss-20b"}):
            pass
    span = next(s for s in finished_spans(exporter) if s.name == "gen")
    assert span.attributes[f"{METADATA_PREFIX}model"] == "gpt-oss-20b"


def test_node_decorator_async(exporter):
    @langperf.node(kind="tool", name="async-fetch")
    async def fetch():
        await asyncio.sleep(0)
        return "ok"

    async def run():
        with langperf.trajectory("outer"):
            return await fetch()

    assert asyncio.run(run()) == "ok"
    spans = {s.name: s for s in finished_spans(exporter)}
    assert "async-fetch" in spans
    assert spans["async-fetch"].attributes[NODE_KIND] == "tool"


def test_node_outside_trajectory_still_records(exporter):
    # A bare node — edge case; should still record a span with no
    # trajectory id. We don't raise just because the user skipped the
    # trajectory scope.
    with langperf.node(kind="tool", name="orphan"):
        pass
    spans = finished_spans(exporter)
    assert len(spans) == 1
    assert spans[0].name == "orphan"
