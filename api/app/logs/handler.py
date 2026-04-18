"""Python logging handler that feeds the in-process ring buffer."""

from __future__ import annotations

import logging

from app.logs.buffer import buffer

_SOURCE_MAP = {
    "langperf": "langperf",
    "uvicorn": "uvicorn",
    "uvicorn.error": "uvicorn",
    "uvicorn.access": "uvicorn",
    "fastapi": "fastapi",
    "sqlalchemy": "sqlalchemy",
    "sqlalchemy.engine": "sqlalchemy",
    "alembic": "alembic",
}


def _source_for(name: str) -> str:
    if name in _SOURCE_MAP:
        return _SOURCE_MAP[name]
    top = (name or "").split(".", 1)[0]
    return _SOURCE_MAP.get(top, top or "root")


class BufferHandler(logging.Handler):
    """Appends every accepted record to the shared LogBuffer."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 — formatting errors must not crash the app
            msg = f"<unformatted log record from {record.name}>"
        if record.exc_info:
            msg = f"{msg}\n{logging.Formatter().formatException(record.exc_info)}"
        buffer.add(
            level=record.levelname,
            source=_source_for(record.name),
            logger=record.name,
            message=msg,
            ts=record.created,
        )


_installed = False


_DIRECT_ATTACH_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "fastapi",
    "sqlalchemy.engine",
    "alembic",
)


def attach_handler(level: int = logging.INFO) -> None:
    """Install the buffer handler globally.

    Most loggers propagate to root, so attaching to root is sufficient. Uvicorn
    sets propagate=False on its own loggers though, so we attach directly to
    the well-known non-propagating loggers that carry useful signal — but only
    when their propagate flag is False, otherwise we'd duplicate every event.

    Safe to call twice.
    """
    global _installed
    if _installed:
        return
    handler = BufferHandler(level=level)
    logging.getLogger().addHandler(handler)
    for name in _DIRECT_ATTACH_LOGGERS:
        lg = logging.getLogger(name)
        if not lg.propagate:
            lg.addHandler(handler)
    _installed = True
