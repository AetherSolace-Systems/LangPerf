"""mark(), metric(), set_user(), current_trajectory_id()."""

from __future__ import annotations

import logging

import langperf
from langperf.attributes import (
    METRIC_PREFIX,
    NODE_KIND,
    NOTES,
    SESSION_ID,
    STATUS_TAG,
    USER_EMAIL,
    USER_ID,
)

from .conftest import finished_spans


def test_mark_tag_and_note_land_on_trajectory_root(exporter):
    with langperf.trajectory("marked"):
        langperf.mark("bad", note="tool returned stale data")

    root = next(s for s in finished_spans(exporter) if s.attributes[NODE_KIND] == "trajectory")
    assert root.attributes[STATUS_TAG] == "bad"
    assert root.attributes[NOTES] == "tool returned stale data"


def test_mark_from_inside_nested_node_still_targets_trajectory(exporter):
    with langperf.trajectory("nested"):
        with langperf.node(kind="tool", name="t1"):
            langperf.mark("interesting")

    root = next(s for s in finished_spans(exporter) if s.attributes[NODE_KIND] == "trajectory")
    # Landed on the trajectory root, NOT on the tool node.
    assert root.attributes[STATUS_TAG] == "interesting"
    tool_span = next(s for s in finished_spans(exporter) if s.name == "t1")
    assert STATUS_TAG not in tool_span.attributes


def test_mark_unknown_tag_still_emitted_with_warning(exporter, caplog):
    with caplog.at_level(logging.WARNING, logger="langperf"):
        with langperf.trajectory("odd"):
            langperf.mark("totally-custom")
    root = next(s for s in finished_spans(exporter) if s.attributes[NODE_KIND] == "trajectory")
    assert root.attributes[STATUS_TAG] == "totally-custom"
    assert any("not in the canonical set" in r.message for r in caplog.records)


def test_mark_outside_trajectory_is_noop(caplog):
    with caplog.at_level(logging.WARNING, logger="langperf"):
        langperf.mark("bad")
    assert any("outside a trajectory" in r.message for r in caplog.records)


def test_mark_with_only_note(exporter):
    with langperf.trajectory("just-note"):
        langperf.mark(note="looked suspicious")
    root = next(s for s in finished_spans(exporter) if s.attributes[NODE_KIND] == "trajectory")
    assert root.attributes[NOTES] == "looked suspicious"
    assert STATUS_TAG not in root.attributes


def test_metric_lands_on_current_span(exporter):
    with langperf.trajectory("metered"):
        with langperf.node(kind="llm", name="classify"):
            langperf.metric("confidence", 0.87)

    span = next(s for s in finished_spans(exporter) if s.name == "classify")
    assert span.attributes[f"{METRIC_PREFIX}confidence"] == 0.87


def test_metric_on_trajectory_when_no_node(exporter):
    # metric() with no active node lands on the trajectory root span
    # because that IS the current span at that scope.
    with langperf.trajectory("root-metric"):
        langperf.metric("retries", 3)

    root = next(s for s in finished_spans(exporter) if s.attributes[NODE_KIND] == "trajectory")
    assert root.attributes[f"{METRIC_PREFIX}retries"] == 3


def test_metric_coerces_non_scalar(exporter):
    with langperf.trajectory("root-metric"):
        langperf.metric("breakdown", {"a": 1})
    root = next(s for s in finished_spans(exporter) if s.attributes[NODE_KIND] == "trajectory")
    assert root.attributes[f"{METRIC_PREFIX}breakdown"] == "{'a': 1}"


def test_set_user_stamps_trajectory_attrs(exporter):
    with langperf.trajectory("late-user"):
        langperf.set_user("u_late", email="l@x.com", session_id="s_x")

    root = next(s for s in finished_spans(exporter) if s.attributes[NODE_KIND] == "trajectory")
    assert root.attributes[USER_ID] == "u_late"
    assert root.attributes[USER_EMAIL] == "l@x.com"
    assert root.attributes[SESSION_ID] == "s_x"


def test_current_trajectory_id_returns_active_id():
    with langperf.trajectory("x") as t:
        assert langperf.current_trajectory_id() == t.id
    assert langperf.current_trajectory_id() is None
