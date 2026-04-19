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


class TrajectoryPatch(BaseModel):
    status_tag: Optional[str] = None
    notes: Optional[str] = None
    clear_tag: bool = False
    clear_notes: bool = False


class NodePatch(BaseModel):
    notes: Optional[str] = None
    clear_notes: bool = False


class FacetsResponse(BaseModel):
    services: list[str]
    environments: list[str]
    tags: list[str]


# ── Agents ────────────────────────────────────────────────────────────────


class AgentVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    git_sha: Optional[str] = None
    short_sha: Optional[str] = None
    package_version: Optional[str] = None
    first_seen_at: datetime
    last_seen_at: datetime


class AgentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    github_url: Optional[str] = None
    language: Optional[str] = None
    token_prefix: Optional[str] = None
    last_token_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AgentDetail(AgentSummary):
    signature: str
    versions: list[AgentVersionSummary] = []


class AgentPatch(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    github_url: Optional[str] = None
    rename_to: Optional[str] = None


class AgentToolUsage(BaseModel):
    tool: str
    calls: int
    errors: int


class LatencyPoint(BaseModel):
    bucket_start: datetime
    runs: int
    p50_latency_ms: Optional[int]
    p95_latency_ms: Optional[int]
    p99_latency_ms: Optional[int]


class AgentMetrics(BaseModel):
    agent: str
    window: str  # "24h" | "7d" | "30d"
    runs: int
    errors: int
    error_rate: float
    p50_latency_ms: Optional[int]
    p95_latency_ms: Optional[int]
    p99_latency_ms: Optional[int]
    total_tokens: int
    latency_series: list[LatencyPoint] = []


class AgentRunRow(BaseModel):
    id: str
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    step_count: int
    token_count: int
    input_tokens: int = 0
    output_tokens: int = 0
    status_tag: Optional[str]
    name: Optional[str]
    environment: Optional[str]
    version_label: Optional[str]
    agent_name: Optional[str] = None


class RunsResponse(BaseModel):
    items: list[AgentRunRow]
    total: int
    limit: int
    offset: int


class AgentRunsResponse(BaseModel):
    items: list[AgentRunRow]
    total: int
    limit: int
    offset: int


# ── Overview (dashboard) ────────────────────────────────────────────────


class OverviewKpi(BaseModel):
    runs: int
    agents: int
    error_rate: float
    p50_latency_ms: Optional[int]
    p95_latency_ms: Optional[int]
    p99_latency_ms: Optional[int]
    flagged: int
    total_tokens: int


class VolumeDay(BaseModel):
    day: datetime
    prod: int
    staging: int
    dev: int
    other: int


class EnvSplit(BaseModel):
    environment: str
    runs: int


class TopTool(BaseModel):
    tool: str
    calls: int
    errors: int


class FlaggedRun(BaseModel):
    id: str
    started_at: datetime
    duration_ms: Optional[int]
    status_tag: Optional[str]
    agent_name: Optional[str]
    summary: Optional[str]


class HeatmapCell(BaseModel):
    agent_name: str
    tool: str
    calls: int


class MostRanAgent(BaseModel):
    name: str
    runs: int
    error_rate: float


class OverviewResponse(BaseModel):
    window: str
    kpi: OverviewKpi
    volume_by_day: list[VolumeDay]
    env_split: list[EnvSplit]
    top_tools: list[TopTool]
    recent_flagged: list[FlaggedRun]
    heatmap: list[HeatmapCell] = []  # deprecated; UI no longer renders
    most_ran_agents: list[MostRanAgent] = []
    latency_series: list[LatencyPoint] = []


class AgentPromptRow(BaseModel):
    text: str
    runs: int
    first_seen_at: datetime
    last_seen_at: datetime


class AgentMiniMetrics(BaseModel):
    runs: int
    error_rate: float
    p95_latency_ms: Optional[int]


class AgentSummaryWithMetrics(AgentSummary):
    metrics: AgentMiniMetrics
    sparkline: list[int] = []
    version_count: int = 0
    environments: list[str] = []
