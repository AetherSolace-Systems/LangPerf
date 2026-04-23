"""Scoring pure-function tests — no DB."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.agent_worklist import score, urgency_bucket, SEVERITY


def test_tool_error_beats_apology_phrase_at_same_count():
    now = datetime.now(timezone.utc)
    tool_err = score(SEVERITY["tool_error"], affected_runs=20, last_seen_at=now)
    apology  = score(SEVERITY["apology_phrase"], affected_runs=20, last_seen_at=now)
    assert tool_err > apology


def test_more_affected_runs_ranks_higher():
    now = datetime.now(timezone.utc)
    ten   = score(SEVERITY["tool_error"], affected_runs=10, last_seen_at=now)
    hundred = score(SEVERITY["tool_error"], affected_runs=100, last_seen_at=now)
    assert hundred > ten


def test_older_issue_decays():
    now = datetime.now(timezone.utc)
    fresh = score(SEVERITY["tool_error"], affected_runs=10, last_seen_at=now)
    week_old = score(
        SEVERITY["tool_error"],
        affected_runs=10,
        last_seen_at=now - timedelta(days=7),
    )
    assert week_old < fresh
    assert 0.4 < week_old / fresh < 0.6  # 1-week half-life


def test_urgency_buckets():
    assert urgency_bucket(10) == "high"
    assert urgency_bucket(6)  == "med"
    assert urgency_bucket(2)  == "low"
    assert urgency_bucket(8)  == "high"
    assert urgency_bucket(4)  == "med"
    assert urgency_bucket(3.9) == "low"
