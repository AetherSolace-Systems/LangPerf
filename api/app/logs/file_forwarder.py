"""Background task that forwards log events to a local JSONL file.

Reads the current log-forwarding config from `workspace_settings` on each
tick; enables or disables itself as the config flips without requiring a
restart. If the config's `file.enabled` is true, every event coming through
the LogBuffer subscription is serialized and appended to the configured
path. Simple rotate-on-day-change based on the local date.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.settings import KEY_LOG_FORWARDING, LogForwardingConfig, _load
from app.db import SessionLocal
from app.logs.buffer import LogEvent, buffer

logger = logging.getLogger("langperf.logs.file_forwarder")

_RELOAD_INTERVAL_SECONDS = 10.0


async def _current_config() -> LogForwardingConfig:
    async with SessionLocal() as session:
        raw = await _load(session, KEY_LOG_FORWARDING)
    if raw is None:
        return LogForwardingConfig()
    return LogForwardingConfig.model_validate(raw)


def _rotate_path(base_path: str, rotate_daily: bool) -> Path:
    p = Path(base_path)
    if not rotate_daily:
        return p
    suffix = datetime.now().strftime("%Y-%m-%d")
    return p.with_name(f"{p.stem}.{suffix}{p.suffix}")


def _prune(base_path: str, keep_days: int) -> None:
    """Delete rotated files older than keep_days."""
    if keep_days <= 0:
        return
    p = Path(base_path)
    parent = p.parent
    if not parent.exists():
        return
    cutoff = datetime.now().timestamp() - keep_days * 86400
    prefix = f"{p.stem}."
    suffix = p.suffix
    for candidate in parent.iterdir():
        if not candidate.is_file():
            continue
        if not candidate.name.startswith(prefix) or not candidate.name.endswith(suffix):
            continue
        try:
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("prune failed for %s: %s", candidate, exc)


async def run() -> None:
    """Long-running background task. Cancellable on shutdown."""
    logger.info("file forwarder started")
    subscription = buffer.subscribe()
    current_config: Optional[LogForwardingConfig] = None
    last_reload = 0.0
    last_prune_day: Optional[str] = None
    try:
        while True:
            now = asyncio.get_event_loop().time()
            if current_config is None or now - last_reload > _RELOAD_INTERVAL_SECONDS:
                try:
                    current_config = await _current_config()
                except Exception as exc:  # noqa: BLE001 — bg task must not die
                    logger.warning("config reload failed: %s", exc)
                last_reload = now

            try:
                event = await asyncio.wait_for(subscription.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue

            if current_config is None or not current_config.file.enabled:
                continue

            target = current_config.file
            path = _rotate_path(target.path, target.rotate_daily)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict()) + "\n")
            except OSError as exc:
                logger.warning("file forwarder write failed to %s: %s", path, exc)

            today = datetime.now().strftime("%Y-%m-%d")
            if target.rotate_daily and last_prune_day != today:
                _prune(target.path, target.keep_days)
                last_prune_day = today
    except asyncio.CancelledError:
        logger.info("file forwarder stopping")
        raise
    finally:
        buffer.unsubscribe(subscription)


def start_background_task() -> asyncio.Task:
    return asyncio.create_task(run(), name="file-forwarder")
