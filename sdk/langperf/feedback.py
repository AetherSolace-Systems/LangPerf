"""langperf.feedback(trajectory_id, thumbs, note=) — end-user thumbs capture.

Fire-and-forget HTTP POST to /v1/feedback. Three retries with 0.25/0.5/1s
backoff then silent drop. Never raises — a broken feedback pipe must never
break the calling application.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Literal, Optional

logger = logging.getLogger("langperf.feedback")

_VALID_THUMBS = ("up", "down")
_RETRY_DELAYS_S = (0.25, 0.5, 1.0)


def feedback(
    trajectory_id: str,
    *,
    thumbs: Literal["up", "down"],
    note: Optional[str] = None,
) -> None:
    """Record end-user thumbs feedback on a trajectory.

    Non-blocking: dispatches to a background thread and returns
    immediately. Retries the HTTP POST up to 3 times with exponential
    backoff (0.25/0.5/1s) then silently drops on persistent failure.

    Args:
        trajectory_id: UUID of the trajectory being rated. Typically you
            obtained this via `langperf.current_trajectory_id()` at the
            moment the agent responded, and stashed it next to the
            message so the user's thumbs click can reference it later.
        thumbs: "up" or "down". Other values raise ValueError synchronously
            so bad developer calls surface immediately.
        note: Optional free-form text reason. Appended to the trajectory's
            notes field server-side.
    """
    if thumbs not in _VALID_THUMBS:
        raise ValueError(
            f"thumbs must be one of {_VALID_THUMBS!r}, got {thumbs!r}"
        )

    token = os.environ.get("LANGPERF_API_TOKEN")
    endpoint = os.environ.get("LANGPERF_ENDPOINT", "http://localhost:4318")
    if not token:
        logger.warning("langperf.feedback: LANGPERF_API_TOKEN unset — dropping feedback")
        return

    body = {"trajectory_id": trajectory_id, "thumbs": thumbs}
    if note is not None:
        body["note"] = note

    thread = threading.Thread(
        target=_post_with_retries,
        args=(f"{endpoint.rstrip('/')}/v1/feedback", token, body),
        daemon=True,
        name="langperf-feedback",
    )
    thread.start()


def _post_with_retries(url: str, token: str, body: dict) -> None:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    for i in range(len(_RETRY_DELAYS_S) + 1):
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if 200 <= resp.status < 300:
                    return
                logger.warning(
                    "langperf.feedback: %s returned HTTP %d", url, resp.status
                )
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            logger.debug("langperf.feedback: attempt %d failed: %s", i + 1, exc)
        if i < len(_RETRY_DELAYS_S):
            time.sleep(_RETRY_DELAYS_S[i])
    logger.info("langperf.feedback: giving up after %d attempts", len(_RETRY_DELAYS_S) + 1)
