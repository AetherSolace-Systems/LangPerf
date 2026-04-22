"""langperf.feedback() POST behavior + retry semantics."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

import langperf


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("LANGPERF_API_TOKEN", "lp_test0000_" + "x" * 32)
    monkeypatch.setenv("LANGPERF_ENDPOINT", "http://langperf-test:4318")


def _wait_for_calls(mock, n, timeout_s=2.0):
    """Poll until the mock has seen n calls or timeout elapses."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if mock.call_count >= n:
            return
        time.sleep(0.01)
    raise AssertionError(
        f"expected >={n} calls, got {mock.call_count} after {timeout_s}s"
    )


def test_feedback_posts_to_feedback_endpoint_with_bearer():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 204
        langperf.feedback("traj-123", thumbs="down")
        _wait_for_calls(mock_urlopen, 1)
        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://langperf-test:4318/v1/feedback"
        assert req.get_header("Authorization").startswith("Bearer lp_test0000_")
        assert req.get_method() == "POST"


def test_feedback_includes_note_in_body():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value.status = 204
        langperf.feedback("traj-123", thumbs="up", note="loved it")
        _wait_for_calls(mock_urlopen, 1)
        req = mock_urlopen.call_args[0][0]
        import json as _json
        body = _json.loads(req.data)
        assert body == {"trajectory_id": "traj-123", "thumbs": "up", "note": "loved it"}


def test_feedback_retries_on_network_error_then_drops():
    import urllib.error
    attempts = []

    def boom(*args, **kwargs):
        attempts.append(time.monotonic())
        raise urllib.error.URLError("network down")

    with patch("urllib.request.urlopen", side_effect=boom):
        langperf.feedback("traj-123", thumbs="down")
        _wait_for_calls_attempts(attempts, 4)

    # Delays 0.25, 0.5, 1.0 s -> total ~1.75s. Allow >=1.4s (some jitter headroom)
    # and cap on the high side so a failing impl doesn't hang the suite.
    total = attempts[-1] - attempts[0]
    assert 1.4 <= total <= 2.5, f"expected retry pacing ~1.75s, got {total:.2f}"


def _wait_for_calls_attempts(lst, n, timeout_s=3.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if len(lst) >= n:
            return
        time.sleep(0.01)
    raise AssertionError(f"expected >={n} attempts, got {len(lst)}")


def test_feedback_never_raises_even_on_5xx():
    with patch("urllib.request.urlopen") as mock_urlopen:
        import urllib.error
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://langperf-test:4318/v1/feedback", 500, "boom", {}, None
        )
        # Must return without raising even after all retries exhaust
        langperf.feedback("traj-123", thumbs="down")
        _wait_for_calls(mock_urlopen, 3)


def test_feedback_rejects_invalid_thumbs():
    # Validation happens BEFORE the background thread kicks off so
    # developer-facing errors surface synchronously.
    with pytest.raises(ValueError, match="thumbs"):
        langperf.feedback("traj-123", thumbs="sideways")
