"""Trajectory __exit__ stamps langperf.completed on the root span."""
from __future__ import annotations

import pytest

import langperf


def _root_completed(spans) -> bool | None:
    """Find the trajectory-root span in an exporter-flushed batch and
    return its completed attribute (None if absent)."""
    for span in spans:
        attrs = span.attributes or {}
        if attrs.get("langperf.node.kind") == "trajectory":
            return attrs.get("langperf.completed")
    return None


def test_clean_exit_stamps_completed_true(exporter):
    with langperf.trajectory("ok-run"):
        pass
    langperf.flush()
    spans = exporter.get_finished_spans()
    assert _root_completed(spans) is True


def test_exception_exit_stamps_completed_false(exporter):
    with pytest.raises(RuntimeError):
        with langperf.trajectory("bad-run"):
            raise RuntimeError("boom")
    langperf.flush()
    spans = exporter.get_finished_spans()
    assert _root_completed(spans) is False
