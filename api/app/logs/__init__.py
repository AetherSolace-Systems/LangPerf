"""In-process log capture for the /logs UI surface."""

from app.logs.buffer import LogBuffer, LogEvent, buffer
from app.logs.handler import attach_handler

__all__ = ["LogBuffer", "LogEvent", "buffer", "attach_handler"]
