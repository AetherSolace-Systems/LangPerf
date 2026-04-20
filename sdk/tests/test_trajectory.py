"""Trajectory context manager — baggage propagation, root span shape, kwargs."""

from __future__ import annotations

import langperf
from langperf.attributes import (
    METADATA_PREFIX,
    NODE_KIND,
    SESSION_ID,
    TRAJECTORY_ID,
    TRAJECTORY_NAME,
    USER_ID,
)

from .conftest import finished_spans


def test_trajectory_emits_root_span_with_kind_and_id(exporter):
    with langperf.trajectory("test-run") as t:
        pass

    spans = finished_spans(exporter)
    assert len(spans) == 1
    root = spans[0]
    assert root.name == "test-run"
    assert root.attributes[NODE_KIND] == "trajectory"
    assert root.attributes[TRAJECTORY_ID] == t.id
    assert root.attributes[TRAJECTORY_NAME] == "test-run"


def test_trajectory_id_propagates_to_child_spans(exporter):
    with langperf.trajectory("outer") as t:
        with langperf.node(kind="tool", name="inner"):
            pass

    spans = finished_spans(exporter)
    by_name = {s.name: s for s in spans}
    # Both the root and the nested node carry the same trajectory id.
    assert by_name["outer"].attributes[TRAJECTORY_ID] == t.id
    assert by_name["inner"].attributes[TRAJECTORY_ID] == t.id


def test_trajectory_user_session_metadata_kwargs(exporter):
    with langperf.trajectory(
        "with-attribution",
        user_id="u_123",
        session_id="s_abc",
        metadata={"feature_flag": "variant_a", "retries": 2},
    ):
        pass

    root = finished_spans(exporter)[0]
    assert root.attributes[USER_ID] == "u_123"
    assert root.attributes[SESSION_ID] == "s_abc"
    assert root.attributes[f"{METADATA_PREFIX}feature_flag"] == "variant_a"
    assert root.attributes[f"{METADATA_PREFIX}retries"] == 2


def test_trajectory_metadata_coerces_non_scalar(exporter):
    with langperf.trajectory("coerce", metadata={"config": {"a": 1}}):
        pass
    root = finished_spans(exporter)[0]
    # dict coerced to str() — we emit *something* rather than drop the field.
    assert root.attributes[f"{METADATA_PREFIX}config"] == "{'a': 1}"


def test_trajectory_set_user_after_enter(exporter):
    with langperf.trajectory("late-user") as t:
        t.set_user("u_late", email="u@x.com", display_name="Late User")
    root = finished_spans(exporter)[0]
    assert root.attributes[USER_ID] == "u_late"
    assert root.attributes["langperf.user.email"] == "u@x.com"
    assert root.attributes["langperf.user.display_name"] == "Late User"


def test_trajectory_without_name_falls_back(exporter):
    with langperf.trajectory():
        pass
    root = finished_spans(exporter)[0]
    assert root.name == "trajectory"
    assert root.attributes[NODE_KIND] == "trajectory"
    # No name set → no TRAJECTORY_NAME attr.
    assert TRAJECTORY_NAME not in root.attributes


def test_trajectory_records_exception(exporter):
    try:
        with langperf.trajectory("fails"):
            raise ValueError("boom")
    except ValueError:
        pass

    root = finished_spans(exporter)[0]
    # OTel records the exception as a span event.
    event_names = [e.name for e in root.events]
    assert "exception" in event_names
