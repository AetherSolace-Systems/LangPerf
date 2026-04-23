"""Caller-provided trajectory.id and `final` kwarg — durable resumption support."""
from __future__ import annotations

import uuid

import pytest

import langperf
from langperf.attributes import COMPLETED, NODE_KIND, TRAJECTORY_ID

from .conftest import finished_spans


def test_caller_provided_id_used_verbatim(exporter):
    run_id = str(uuid.uuid4())
    with langperf.trajectory("seg-1", id=run_id) as t:
        pass

    assert t.id == run_id
    root = finished_spans(exporter)[0]
    assert root.attributes[TRAJECTORY_ID] == run_id


def test_caller_provided_id_propagates_to_children(exporter):
    run_id = str(uuid.uuid4())
    with langperf.trajectory("seg-1", id=run_id):
        with langperf.node(kind="tool", name="inner"):
            pass
    spans = finished_spans(exporter)
    by_name = {s.name: s for s in spans}
    assert by_name["seg-1"].attributes[TRAJECTORY_ID] == run_id
    assert by_name["inner"].attributes[TRAJECTORY_ID] == run_id


def test_invalid_id_raises_value_error(exporter):
    with pytest.raises(ValueError):
        with langperf.trajectory("bad-id", id="not-a-uuid"):
            pass
    # No root span was opened because __enter__ raised before the span.
    assert finished_spans(exporter) == []


def test_two_sequential_blocks_sharing_id_emit_two_roots(exporter):
    run_id = str(uuid.uuid4())
    with langperf.trajectory("run", id=run_id):
        pass
    with langperf.trajectory("run", id=run_id):
        pass
    roots = [
        s
        for s in finished_spans(exporter)
        if s.attributes.get(NODE_KIND) == "trajectory"
    ]
    assert len(roots) == 2
    assert {r.attributes[TRAJECTORY_ID] for r in roots} == {run_id}


def test_default_behavior_unchanged_when_id_not_provided(exporter):
    """Regression guard: omitting `id=` must still autogenerate a UUID."""
    with langperf.trajectory("auto") as t:
        pass
    assert uuid.UUID(t.id)  # parses cleanly
    root = finished_spans(exporter)[0]
    assert root.attributes[TRAJECTORY_ID] == t.id


def test_final_false_does_not_stamp_completed(exporter):
    with langperf.trajectory("seg-mid", final=False):
        pass
    root = finished_spans(exporter)[0]
    assert COMPLETED not in root.attributes


def test_final_false_does_not_stamp_completed_on_exception(exporter):
    with pytest.raises(RuntimeError):
        with langperf.trajectory("seg-mid-fail", final=False):
            raise RuntimeError("mid-segment boom")
    root = finished_spans(exporter)[0]
    # Even on exception, non-final segment leaves completed unset so a
    # later final segment can authoritatively stamp the run's outcome.
    assert COMPLETED not in root.attributes


def test_final_true_default_still_stamps_completed(exporter):
    with langperf.trajectory("seg-final"):
        pass
    root = finished_spans(exporter)[0]
    assert root.attributes[COMPLETED] is True


def test_final_true_stamps_false_on_exception(exporter):
    with pytest.raises(RuntimeError):
        with langperf.trajectory("seg-final-fail", final=True):
            raise RuntimeError("boom")
    root = finished_spans(exporter)[0]
    assert root.attributes[COMPLETED] is False
