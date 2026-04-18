"""/api/logs — recent history + SSE live stream."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.logs import buffer
from app.logs.buffer import LogEvent

router = APIRouter(prefix="/api/logs")


class LogEventOut(BaseModel):
    ts: float
    level: str
    source: str
    logger: str
    message: str
    seq: int


def _match(
    event: LogEvent,
    *,
    sources: Optional[set[str]],
    min_level: Optional[int],
    q: Optional[str],
) -> bool:
    if sources and event.source not in sources:
        return False
    if min_level is not None and _LEVEL_RANK.get(event.level, 20) < min_level:
        return False
    if q and q.lower() not in event.message.lower():
        return False
    return True


_LEVEL_RANK = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "WARN": 30, "ERROR": 40, "CRITICAL": 50}


def _parse_level(level: Optional[str]) -> Optional[int]:
    if not level:
        return None
    return _LEVEL_RANK.get(level.upper())


def _parse_sources(s: Optional[str]) -> Optional[set[str]]:
    if not s:
        return None
    parts = {p.strip() for p in s.split(",") if p.strip()}
    return parts or None


@router.get("/recent", response_model=list[LogEventOut])
async def recent_logs(
    limit: int = Query(default=500, ge=1, le=5000),
    source: Optional[str] = Query(default=None, description="csv of source tags"),
    level: Optional[str] = Query(default=None, description="min level: INFO|WARN|ERROR"),
    q: Optional[str] = Query(default=None, description="substring search"),
) -> list[LogEventOut]:
    sources = _parse_sources(source)
    min_level = _parse_level(level)
    events = buffer.recent(limit=limit * 4)  # over-fetch to account for filters
    filtered = [
        e for e in events
        if _match(e, sources=sources, min_level=min_level, q=q)
    ]
    # Return the most recent `limit` after filtering.
    return [LogEventOut(**e.to_dict()) for e in filtered[-limit:]]


@router.get("/stream")
async def stream_logs(
    request: Request,
    source: Optional[str] = Query(default=None),
    level: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
) -> StreamingResponse:
    sources = _parse_sources(source)
    min_level = _parse_level(level)

    async def gen() -> AsyncIterator[bytes]:
        subscription = buffer.subscribe()
        try:
            # Keepalive on connect so the client confirms the stream is open.
            yield b": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(subscription.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # Periodic comment keeps proxies from closing an idle stream.
                    yield b": keepalive\n\n"
                    continue
                if not _match(event, sources=sources, min_level=min_level, q=q):
                    continue
                payload = json.dumps(event.to_dict())
                yield f"data: {payload}\n\n".encode("utf-8")
        finally:
            buffer.unsubscribe(subscription)

    return StreamingResponse(gen(), media_type="text/event-stream")
