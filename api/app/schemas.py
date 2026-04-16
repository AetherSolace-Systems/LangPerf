"""Pydantic response schemas for the UI API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class SpanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    span_id: str
    trace_id: str
    trajectory_id: str
    parent_span_id: Optional[str]
    name: str
    kind: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    attributes: dict[str, Any]
    events: Optional[list[Any]]
    status_code: Optional[str]
    notes: Optional[str]


class TrajectorySummary(BaseModel):
    """List-view shape — omits full spans."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    trace_id: Optional[str]
    service_name: str
    environment: Optional[str]
    name: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    status_tag: Optional[str]
    notes: Optional[str]
    step_count: int
    token_count: int
    duration_ms: Optional[int]


class TrajectoryDetail(TrajectorySummary):
    """Detail-view shape — includes all spans."""

    spans: list[SpanOut]


class TrajectoryListResponse(BaseModel):
    items: list[TrajectorySummary]
    total: int
    limit: int
    offset: int
