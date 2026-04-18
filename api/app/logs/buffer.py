"""In-process ring buffer for structured log events.

Single process, single instance. Every emitted log record gets appended to
a bounded deque (capped at BUFFER_SIZE), and any active SSE subscribers
receive it via their asyncio.Queue. Subscribers are created per SSE
connection and dropped on disconnect.
"""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Iterator

BUFFER_SIZE = 10_000
_QUEUE_MAX = 2_000  # per-subscriber; overflow drops silently


@dataclass(frozen=True, slots=True)
class LogEvent:
    ts: float          # unix seconds, fractional
    level: str         # "INFO" | "WARN" | "ERROR" | "DEBUG" | "CRITICAL"
    source: str        # short source tag — top-level logger segment
    logger: str        # full logger name for debugging
    message: str       # already-formatted message
    seq: int = 0       # monotonic id for client-side de-dup

    def to_dict(self) -> dict:
        return asdict(self)


class LogBuffer:
    def __init__(self, maxlen: int = BUFFER_SIZE) -> None:
        self._events: deque[LogEvent] = deque(maxlen=maxlen)
        self._subscribers: list[asyncio.Queue[LogEvent]] = []
        self._seq: int = 0

    def add(self, level: str, source: str, logger: str, message: str, ts: float) -> None:
        self._seq += 1
        event = LogEvent(
            ts=ts,
            level=level,
            source=source,
            logger=logger,
            message=message,
            seq=self._seq,
        )
        self._events.append(event)
        # Fan out to live subscribers. Drop on back-pressure rather than block.
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def recent(self, limit: int = 500) -> list[LogEvent]:
        # deque supports slicing via list() conversion; cheap at 10k items.
        if limit >= len(self._events):
            return list(self._events)
        return list(self._events)[-limit:]

    def subscribe(self) -> asyncio.Queue[LogEvent]:
        q: asyncio.Queue[LogEvent] = asyncio.Queue(maxsize=_QUEUE_MAX)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[LogEvent]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def __iter__(self) -> Iterator[LogEvent]:
        return iter(self._events)


buffer = LogBuffer()
