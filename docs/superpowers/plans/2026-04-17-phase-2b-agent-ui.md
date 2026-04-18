# Phase 2b — Agent UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 1 placeholder pages (`/`, `/agents`, `/agents/[name]/overview`) with real data-driven UI that consumes the Phase 2a endpoints. The Dashboard shows big-picture metrics across all agents. The Agents index shows a card grid. The Agent-detail Overview tab shows identity strip + KPIs + run-volume chart + p50/p95/p99 latency + tokens+cost + per-agent tools + recent runs table.

**Architecture:** One new backend aggregation endpoint (`/api/overview`) avoids N+1 per-agent queries on the dashboard. `/api/agents` gets enriched with mini-metrics so the Agents index + Dashboard's agent grid render without extra round-trips. All charts are inline SVG (no charting library) matching the brainstorm mockups. Server components fetch on page load — no client-side polling in v1; the existing auto-refresh concept is deferred to Phase 4.

**Tech Stack:** Next.js 14 app router, React 18, TypeScript, Tailwind, inline SVG charts. Backend: FastAPI + SQLAlchemy 2.0 async.

---

## File Structure

**New files:**
- `api/app/api/overview.py` — `/api/overview` aggregation endpoint
- `web/components/charts/bar-chart.tsx` — vertical stacked-bar (run volume × time)
- `web/components/charts/line-chart.tsx` — multi-line chart with axes (latency p50/p95/p99)
- `web/components/charts/sparkline.tsx` — tiny inline SVG for agent-card sparklines
- `web/components/charts/tokens-cost-chart.tsx` — dual-axis stacked-bar + line (tokens + cost)
- `web/components/dashboard/kpi-strip.tsx` — 5-tile KPI row
- `web/components/dashboard/agent-grid.tsx` — reusable grid of agent cards
- `web/components/dashboard/top-tools.tsx` — horizontal-bar tool list
- `web/components/dashboard/recent-flagged.tsx` — flagged runs table
- `web/components/dashboard/tool-agent-heatmap.tsx` — tools-by-agents heatmap
- `web/components/dashboard/env-split.tsx` — environment horizontal-bar breakdown
- `web/components/agent/identity-strip.tsx` — reusable identity strip (agent, version, env, live KPIs)
- `web/components/agent/runs-table.tsx` — reusable datetime/tokens/cost/latency/status table
- `web/components/agent/time-range-picker.tsx` — 24h / 7d / 30d segmented picker

**Modified files:**
- `api/app/api/agents.py` — extend list_agents to include mini-metrics via a `with_metrics` query param
- `api/app/schemas.py` — add `AgentSummaryWithMetrics`, `OverviewResponse`, and supporting sub-models
- `api/app/main.py` — register overview_router
- `web/lib/api.ts` — add Agent/Metrics/Overview types + client functions
- `web/app/page.tsx` — replace Dashboard placeholder with real content
- `web/app/agents/page.tsx` — replace Agents index placeholder with real cards
- `web/app/agents/[name]/[tab]/page.tsx` — Overview tab consumes real data; other tabs still placeholder

**Unchanged from Phase 1/2a:**
- Rail, TopBar, ContextSidebar, AppShell, Chip, nav-config, palette, run-detail (`/t/[id]`), History, Logs, Settings.
- All v2 teasers remain visually identical — only the 3 Dashboard teasers + 3 Agent-detail teasers (already built in Phase 1) get reused.

---

### Task 1: Backend — `/api/overview` aggregation endpoint

**Files:**
- Create: `api/app/api/overview.py`
- Modify: `api/app/schemas.py` — add `OverviewResponse` + nested types
- Modify: `api/app/main.py` — include router

- [ ] **Step 1: Append to `api/app/schemas.py`**

```python


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
    day: datetime  # truncated to midnight UTC for the bucket
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
    summary: Optional[str]  # derived from trajectory.name or first user message


class HeatmapCell(BaseModel):
    agent_name: str
    tool: str
    calls: int


class OverviewResponse(BaseModel):
    window: str
    kpi: OverviewKpi
    volume_by_day: list[VolumeDay]
    env_split: list[EnvSplit]
    top_tools: list[TopTool]
    recent_flagged: list[FlaggedRun]
    heatmap: list[HeatmapCell]
```

- [ ] **Step 2: Create `api/app/api/overview.py`**

```python
"""Dashboard aggregation endpoint — scopes counts, tools, and heatmap
across every agent ingested into this workspace.

Designed to fit on a single HTTP response so the Dashboard is one fetch.
All aggregates bucketed by the `window` query param (24h / 7d / 30d).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Agent, Span, Trajectory
from app.schemas import (
    EnvSplit,
    FlaggedRun,
    HeatmapCell,
    OverviewKpi,
    OverviewResponse,
    TopTool,
    VolumeDay,
)

router = APIRouter(prefix="/api/overview")

_WINDOW_DELTA = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@router.get("", response_model=OverviewResponse)
async def get_overview(
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
) -> OverviewResponse:
    since = datetime.now(tz=timezone.utc) - _WINDOW_DELTA[window]

    # ── KPI block ────────────────────────────────────────────────────────
    runs = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since
            )
        )
    ).scalar_one()

    agents = (
        await session.execute(
            select(func.count(func.distinct(Trajectory.agent_id))).where(
                Trajectory.agent_id.is_not(None),
                Trajectory.started_at >= since,
            )
        )
    ).scalar_one()

    flagged = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since,
                Trajectory.status_tag.is_not(None),
            )
        )
    ).scalar_one()

    errors = (
        await session.execute(
            select(func.count()).select_from(Trajectory).where(
                Trajectory.started_at >= since,
                Trajectory.status_tag == "bad",
            )
        )
    ).scalar_one()

    total_tokens = (
        await session.execute(
            select(func.coalesce(func.sum(Trajectory.token_count), 0)).where(
                Trajectory.started_at >= since
            )
        )
    ).scalar_one()

    p_rows = (
        await session.execute(
            select(
                func.percentile_cont(0.50)
                .within_group(Trajectory.duration_ms.asc())
                .label("p50"),
                func.percentile_cont(0.95)
                .within_group(Trajectory.duration_ms.asc())
                .label("p95"),
                func.percentile_cont(0.99)
                .within_group(Trajectory.duration_ms.asc())
                .label("p99"),
            ).where(
                Trajectory.started_at >= since,
                Trajectory.duration_ms.is_not(None),
            )
        )
    ).one()

    def _to_int(x: object) -> Optional[int]:
        return None if x is None else int(x)

    kpi = OverviewKpi(
        runs=int(runs),
        agents=int(agents),
        error_rate=(float(errors) / float(runs)) if runs else 0.0,
        p50_latency_ms=_to_int(p_rows.p50),
        p95_latency_ms=_to_int(p_rows.p95),
        p99_latency_ms=_to_int(p_rows.p99),
        flagged=int(flagged),
        total_tokens=int(total_tokens),
    )

    # ── Volume by day × environment ──────────────────────────────────────
    day_bucket = func.date_trunc("day", Trajectory.started_at).label("day")
    vol_rows = (
        await session.execute(
            select(
                day_bucket,
                Trajectory.environment,
                func.count().label("n"),
            )
            .where(Trajectory.started_at >= since)
            .group_by("day", Trajectory.environment)
            .order_by("day")
        )
    ).all()

    by_day: dict[datetime, dict[str, int]] = {}
    for day, env, n in vol_rows:
        bucket = by_day.setdefault(day, {"prod": 0, "staging": 0, "dev": 0, "other": 0})
        key = env if env in ("prod", "staging", "dev") else "other"
        bucket[key] += int(n)

    volume_by_day = [
        VolumeDay(
            day=day,
            prod=bucket["prod"],
            staging=bucket["staging"],
            dev=bucket["dev"],
            other=bucket["other"],
        )
        for day, bucket in sorted(by_day.items())
    ]

    # ── Env split ────────────────────────────────────────────────────────
    env_rows = (
        await session.execute(
            select(
                func.coalesce(Trajectory.environment, "—"),
                func.count(),
            )
            .where(Trajectory.started_at >= since)
            .group_by(Trajectory.environment)
            .order_by(func.count().desc())
        )
    ).all()
    env_split = [EnvSplit(environment=e, runs=int(n)) for e, n in env_rows]

    # ── Top tools across all agents ──────────────────────────────────────
    tool_rows = (
        await session.execute(
            select(
                Span.name.label("tool"),
                func.count().label("calls"),
                func.sum(
                    func.cast(Span.status_code == "ERROR", Integer)
                ).label("errors"),
            )
            .join(Trajectory, Trajectory.id == Span.trajectory_id)
            .where(
                Trajectory.started_at >= since,
                Span.kind.in_(("tool", "tool_call")),
            )
            .group_by(Span.name)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    top_tools = [
        TopTool(tool=row.tool, calls=int(row.calls), errors=int(row.errors or 0))
        for row in tool_rows
    ]

    # ── Recent flagged runs ──────────────────────────────────────────────
    flagged_rows = (
        await session.execute(
            select(Trajectory, Agent.name)
            .outerjoin(Agent, Agent.id == Trajectory.agent_id)
            .where(
                Trajectory.started_at >= since,
                Trajectory.status_tag.is_not(None),
            )
            .order_by(Trajectory.started_at.desc())
            .limit(10)
        )
    ).all()
    recent_flagged = [
        FlaggedRun(
            id=traj.id,
            started_at=traj.started_at,
            duration_ms=traj.duration_ms,
            status_tag=traj.status_tag,
            agent_name=agent_name,
            summary=traj.name,
        )
        for traj, agent_name in flagged_rows
    ]

    # ── Tool-by-agent heatmap (top 6 agents × top 6 tools) ───────────────
    top_agents = (
        await session.execute(
            select(Agent.name, func.count().label("n"))
            .join(Trajectory, Trajectory.agent_id == Agent.id)
            .where(Trajectory.started_at >= since)
            .group_by(Agent.name)
            .order_by(func.count().desc())
            .limit(6)
        )
    ).all()
    agent_names = [row.name for row in top_agents]
    top_tool_names = [t.tool for t in top_tools[:6]]

    if agent_names and top_tool_names:
        hm_rows = (
            await session.execute(
                select(
                    Agent.name.label("agent_name"),
                    Span.name.label("tool"),
                    func.count().label("calls"),
                )
                .join(Trajectory, Trajectory.id == Span.trajectory_id)
                .join(Agent, Agent.id == Trajectory.agent_id)
                .where(
                    Trajectory.started_at >= since,
                    Span.kind.in_(("tool", "tool_call")),
                    Agent.name.in_(agent_names),
                    Span.name.in_(top_tool_names),
                )
                .group_by(Agent.name, Span.name)
            )
        ).all()
        heatmap = [
            HeatmapCell(agent_name=row.agent_name, tool=row.tool, calls=int(row.calls))
            for row in hm_rows
        ]
    else:
        heatmap = []

    return OverviewResponse(
        window=window,
        kpi=kpi,
        volume_by_day=volume_by_day,
        env_split=env_split,
        top_tools=top_tools,
        recent_flagged=recent_flagged,
        heatmap=heatmap,
    )
```

- [ ] **Step 3: Register the router in `api/app/main.py`**

Add to the imports:
```python
from app.api.overview import router as overview_router
```

And at the bottom, after the other `app.include_router(...)` calls:
```python
app.include_router(overview_router)
```

- [ ] **Step 4: Restart + smoke test**

```bash
cd /Users/andrewlavoie/code/langperf
docker compose restart langperf-api
sleep 5
curl -s "http://localhost:4318/api/overview?window=30d" | python3 -m json.tool | head -80
```

Expected: valid JSON with all seven top-level keys (`window`, `kpi`, `volume_by_day`, `env_split`, `top_tools`, `recent_flagged`, `heatmap`). `kpi.runs` should be > 0 given the seeded data.

- [ ] **Step 5: Commit**

```bash
git add api/app/schemas.py api/app/api/overview.py api/app/main.py
git commit -m "api: /api/overview — dashboard aggregation in one fetch"
```

---

### Task 2: Backend — enrich `/api/agents` with mini-metrics

**Files:**
- Modify: `api/app/api/agents.py` — list_agents accepts `?with_metrics=true`
- Modify: `api/app/schemas.py` — add `AgentMiniMetrics` + extend `AgentSummary` (or add `AgentSummaryWithMetrics`)

- [ ] **Step 1: Append to `api/app/schemas.py`**

```python


class AgentMiniMetrics(BaseModel):
    runs: int
    error_rate: float
    p95_latency_ms: Optional[int]


class AgentSummaryWithMetrics(AgentSummary):
    metrics: AgentMiniMetrics
    # 7-day sparkline: one integer per day (runs count). Length ≤ 8.
    sparkline: list[int] = []
    version_count: int = 0
    environments: list[str] = []  # distinct environments seen in-window
```

- [ ] **Step 2: Extend `list_agents` in `api/app/api/agents.py`**

Replace the current `list_agents` handler with:

```python
@router.get("", response_model=list[AgentSummary] | list[AgentSummaryWithMetrics])
async def list_agents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    with_metrics: bool = Query(default=False),
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Agent).order_by(Agent.name).limit(limit).offset(offset)
    )
    agents = list(result.scalars().all())

    if not with_metrics:
        return [AgentSummary.model_validate(a) for a in agents]

    since = datetime.now(tz=timezone.utc) - _WINDOW_DELTA[window]

    # One bulk query per metric type — still O(agents) rows returned but
    # O(1) round-trips.
    runs_by_agent = {
        row.agent_id: int(row.n)
        for row in (
            await session.execute(
                select(
                    Trajectory.agent_id,
                    func.count().label("n"),
                )
                .where(
                    Trajectory.agent_id.is_not(None),
                    Trajectory.started_at >= since,
                )
                .group_by(Trajectory.agent_id)
            )
        ).all()
    }

    errors_by_agent = {
        row.agent_id: int(row.n)
        for row in (
            await session.execute(
                select(
                    Trajectory.agent_id,
                    func.count().label("n"),
                )
                .where(
                    Trajectory.agent_id.is_not(None),
                    Trajectory.started_at >= since,
                    Trajectory.status_tag == "bad",
                )
                .group_by(Trajectory.agent_id)
            )
        ).all()
    }

    p95_by_agent = {
        row.agent_id: int(row.p95) if row.p95 is not None else None
        for row in (
            await session.execute(
                select(
                    Trajectory.agent_id,
                    func.percentile_cont(0.95)
                    .within_group(Trajectory.duration_ms.asc())
                    .label("p95"),
                )
                .where(
                    Trajectory.agent_id.is_not(None),
                    Trajectory.started_at >= since,
                    Trajectory.duration_ms.is_not(None),
                )
                .group_by(Trajectory.agent_id)
            )
        ).all()
    }

    # Sparkline: runs per day-bucket for each agent (last 8 days / 24 hours / 30 days).
    day_bucket = func.date_trunc("day", Trajectory.started_at).label("day")
    spark_rows = (
        await session.execute(
            select(
                Trajectory.agent_id,
                day_bucket,
                func.count().label("n"),
            )
            .where(
                Trajectory.agent_id.is_not(None),
                Trajectory.started_at >= since,
            )
            .group_by(Trajectory.agent_id, "day")
            .order_by(Trajectory.agent_id, "day")
        )
    ).all()
    spark_by_agent: dict[str, list[int]] = {}
    for agent_id, _day, n in spark_rows:
        spark_by_agent.setdefault(agent_id, []).append(int(n))

    version_count_by_agent = {
        row.agent_id: int(row.n)
        for row in (
            await session.execute(
                select(
                    AgentVersion.agent_id,
                    func.count().label("n"),
                ).group_by(AgentVersion.agent_id)
            )
        ).all()
    }

    envs_by_agent: dict[str, list[str]] = {}
    env_rows = (
        await session.execute(
            select(Trajectory.agent_id, Trajectory.environment)
            .where(
                Trajectory.agent_id.is_not(None),
                Trajectory.started_at >= since,
                Trajectory.environment.is_not(None),
            )
            .distinct()
        )
    ).all()
    for agent_id, env in env_rows:
        envs_by_agent.setdefault(agent_id, []).append(env)

    out: list[AgentSummaryWithMetrics] = []
    for a in agents:
        runs = runs_by_agent.get(a.id, 0)
        errors = errors_by_agent.get(a.id, 0)
        out.append(
            AgentSummaryWithMetrics(
                **AgentSummary.model_validate(a).model_dump(),
                metrics=AgentMiniMetrics(
                    runs=runs,
                    error_rate=(errors / runs) if runs else 0.0,
                    p95_latency_ms=p95_by_agent.get(a.id),
                ),
                sparkline=spark_by_agent.get(a.id, []),
                version_count=version_count_by_agent.get(a.id, 0),
                environments=sorted(envs_by_agent.get(a.id, [])),
            )
        )
    return out
```

Make sure the imports at the top of `api/app/api/agents.py` include `AgentSummaryWithMetrics` and `AgentMiniMetrics` from `app.schemas`. If not already added from Task 9, they are now.

- [ ] **Step 3: Restart + smoke test**

```bash
docker compose restart langperf-api
sleep 4
curl -s "http://localhost:4318/api/agents?with_metrics=true&window=30d" | python3 -m json.tool | head -40
```

Expected: each object has `metrics { runs, error_rate, p95_latency_ms }`, plus `sparkline`, `version_count`, `environments`.

- [ ] **Step 4: Commit**

```bash
git add api/app/schemas.py api/app/api/agents.py
git commit -m "api: /api/agents?with_metrics=true — embed mini-metrics + sparkline"
```

---

### Task 3: Web API client types + functions

**Files:**
- Modify: `web/lib/api.ts`

- [ ] **Step 1: Append to `web/lib/api.ts`**

Before the `listTrajectories` function, append these types + functions. Preserve everything above.

```typescript
// ── Agents (Phase 2b) ─────────────────────────────────────────────────

export type AgentMiniMetrics = {
  runs: number;
  error_rate: number;
  p95_latency_ms: number | null;
};

export type AgentSummary = {
  id: string;
  name: string;
  display_name: string | null;
  description: string | null;
  owner: string | null;
  github_url: string | null;
  language: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentSummaryWithMetrics = AgentSummary & {
  metrics: AgentMiniMetrics;
  sparkline: number[];
  version_count: number;
  environments: string[];
};

export type AgentVersionSummary = {
  id: string;
  label: string;
  git_sha: string | null;
  short_sha: string | null;
  package_version: string | null;
  first_seen_at: string;
  last_seen_at: string;
};

export type AgentDetail = AgentSummary & {
  signature: string;
  versions: AgentVersionSummary[];
};

export type AgentMetrics = {
  agent: string;
  window: string;
  runs: number;
  errors: number;
  error_rate: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  total_tokens: number;
};

export type AgentToolUsage = {
  tool: string;
  calls: number;
  errors: number;
};

export type AgentRunRow = {
  id: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  step_count: number;
  token_count: number;
  status_tag: string | null;
  name: string | null;
  environment: string | null;
  version_label: string | null;
};

export type AgentRunsResponse = {
  items: AgentRunRow[];
  total: number;
  limit: number;
  offset: number;
};

// ── Overview ─────────────────────────────────────────────────────────

export type OverviewKpi = {
  runs: number;
  agents: number;
  error_rate: number;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  p99_latency_ms: number | null;
  flagged: number;
  total_tokens: number;
};

export type VolumeDay = {
  day: string;
  prod: number;
  staging: number;
  dev: number;
  other: number;
};

export type EnvSplit = { environment: string; runs: number };
export type TopTool = { tool: string; calls: number; errors: number };
export type FlaggedRun = {
  id: string;
  started_at: string;
  duration_ms: number | null;
  status_tag: string | null;
  agent_name: string | null;
  summary: string | null;
};
export type HeatmapCell = { agent_name: string; tool: string; calls: number };

export type OverviewResponse = {
  window: string;
  kpi: OverviewKpi;
  volume_by_day: VolumeDay[];
  env_split: EnvSplit[];
  top_tools: TopTool[];
  recent_flagged: FlaggedRun[];
  heatmap: HeatmapCell[];
};

export type TimeWindow = "24h" | "7d" | "30d";

// ── Fetch functions ──────────────────────────────────────────────────

export async function getOverview(window: TimeWindow = "7d"): Promise<OverviewResponse> {
  return apiFetch<OverviewResponse>(`/api/overview?window=${window}`);
}

export async function listAgents(
  opts: { with_metrics?: boolean; window?: TimeWindow } = {},
): Promise<AgentSummary[] | AgentSummaryWithMetrics[]> {
  const p = new URLSearchParams();
  if (opts.with_metrics) p.set("with_metrics", "true");
  if (opts.window) p.set("window", opts.window);
  const q = p.toString();
  return apiFetch<AgentSummary[] | AgentSummaryWithMetrics[]>(
    `/api/agents${q ? `?${q}` : ""}`,
  );
}

export async function getAgent(name: string): Promise<AgentDetail> {
  return apiFetch<AgentDetail>(`/api/agents/${encodeURIComponent(name)}`);
}

export async function getAgentMetrics(
  name: string,
  window: TimeWindow = "7d",
): Promise<AgentMetrics> {
  return apiFetch<AgentMetrics>(
    `/api/agents/${encodeURIComponent(name)}/metrics?window=${window}`,
  );
}

export async function getAgentTools(
  name: string,
  window: TimeWindow = "7d",
): Promise<AgentToolUsage[]> {
  return apiFetch<AgentToolUsage[]>(
    `/api/agents/${encodeURIComponent(name)}/tools?window=${window}`,
  );
}

export async function getAgentRuns(
  name: string,
  opts: { limit?: number; offset?: number; environment?: string; version?: string } = {},
): Promise<AgentRunsResponse> {
  const p = new URLSearchParams();
  if (opts.limit != null) p.set("limit", String(opts.limit));
  if (opts.offset != null) p.set("offset", String(opts.offset));
  if (opts.environment) p.set("environment", opts.environment);
  if (opts.version) p.set("version", opts.version);
  const q = p.toString();
  return apiFetch<AgentRunsResponse>(
    `/api/agents/${encodeURIComponent(name)}/runs${q ? `?${q}` : ""}`,
  );
}
```

- [ ] **Step 2: Type-check + commit**

```bash
cd /Users/andrewlavoie/code/langperf/web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/lib/api.ts
git commit -m "web: add Phase 2b agent + overview API client types and functions"
```

---

### Task 4: Chart primitives (inline SVG)

**Files:**
- Create: `web/components/charts/sparkline.tsx`
- Create: `web/components/charts/line-chart.tsx`
- Create: `web/components/charts/bar-chart.tsx`
- Create: `web/components/charts/tokens-cost-chart.tsx`

- [ ] **Step 1: Create `web/components/charts/sparkline.tsx`**

```tsx
import type { CSSProperties } from "react";

/** Tiny inline sparkline — one polyline over a fixed 100×30 viewBox. */
export function Sparkline({
  values,
  stroke = "#6BBAB1",
  strokeWidth = 1.2,
  height = 30,
  className,
}: {
  values: number[];
  stroke?: string;
  strokeWidth?: number;
  height?: number;
  className?: string;
}) {
  if (values.length === 0) {
    return (
      <svg
        viewBox="0 0 100 30"
        preserveAspectRatio="none"
        className={className}
        style={{ width: "100%", height } as CSSProperties}
        aria-hidden="true"
      />
    );
  }
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const step = values.length > 1 ? 100 / (values.length - 1) : 0;
  const points = values
    .map((v, i) => {
      const x = i * step;
      const y = 30 - ((v - min) / range) * 26 - 2;
      return `${x},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 30"
      preserveAspectRatio="none"
      className={className}
      style={{ width: "100%", height } as CSSProperties}
      aria-hidden="true"
    >
      <polyline points={points} fill="none" stroke={stroke} strokeWidth={strokeWidth} />
    </svg>
  );
}
```

- [ ] **Step 2: Create `web/components/charts/line-chart.tsx`**

```tsx
/** Multi-line chart with axes. Y-axis labels on the left, X-axis labels
 *  beneath. `lines` is an array of named series sharing the same X-domain. */
export type LineSeries = {
  name: string;
  color: string;
  values: number[];
};

export function LineChart({
  lines,
  xLabels,
  yTicks,
  yFormat,
  height = 150,
}: {
  lines: LineSeries[];
  xLabels: string[];
  yTicks: number[]; // numeric y-axis ticks, ordered ascending
  yFormat: (v: number) => string;
  height?: number;
}) {
  const vw = 240; // SVG viewBox width
  const vh = 130; // SVG viewBox height (before axis labels)
  const maxY = yTicks[yTicks.length - 1] ?? 1;
  const toY = (v: number) => vh - (v / maxY) * vh;
  return (
    <div className="relative" style={{ height }}>
      <div
        className="absolute left-0 top-0 bottom-[18px] w-[40px] flex flex-col justify-between font-mono text-[9px] text-patina"
      >
        {[...yTicks].reverse().map((t) => (
          <span key={t} className="text-right pr-[6px]">
            {yFormat(t)}
          </span>
        ))}
      </div>
      <div className="absolute left-[40px] right-0 top-0 bottom-[18px] border-l border-b border-[color:var(--border)]">
        <svg viewBox={`0 0 ${vw} ${vh}`} preserveAspectRatio="none" className="w-full h-full">
          {yTicks.slice(0, -1).map((t) => (
            <line
              key={t}
              x1={0}
              x2={vw}
              y1={toY(t)}
              y2={toY(t)}
              stroke="#2E3A40"
              strokeDasharray="2,3"
            />
          ))}
          {lines.map((s) => {
            if (s.values.length === 0) return null;
            const step = s.values.length > 1 ? vw / (s.values.length - 1) : 0;
            const points = s.values
              .map((v, i) => `${i * step},${toY(v).toFixed(2)}`)
              .join(" ");
            return (
              <polyline
                key={s.name}
                points={points}
                fill="none"
                stroke={s.color}
                strokeWidth={1.5}
              />
            );
          })}
        </svg>
      </div>
      <div className="absolute left-[40px] right-0 bottom-0 flex justify-between font-mono text-[9px] text-patina">
        {xLabels.map((label, i) => (
          <span key={`${label}-${i}`}>{label}</span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `web/components/charts/bar-chart.tsx`**

```tsx
/** Stacked vertical bar chart. Each `bars` entry is one column; `segments`
 *  within a bar stack bottom-up. */
export type BarSegment = { color: string; value: number };
export type BarColumn = { label: string; segments: BarSegment[] };

export function StackedBarChart({
  bars,
  height = 120,
}: {
  bars: BarColumn[];
  height?: number;
}) {
  const max = Math.max(
    1,
    ...bars.map((b) => b.segments.reduce((s, seg) => s + seg.value, 0)),
  );
  return (
    <div className="flex flex-col gap-[6px]" style={{ height }}>
      <div className="flex items-end h-full gap-[4px]">
        {bars.map((b) => (
          <div key={b.label} className="flex-1 flex flex-col-reverse gap-[1px] h-full">
            {b.segments.map((seg, i) => {
              const hPct = (seg.value / max) * 100;
              return (
                <div
                  key={i}
                  style={{ background: seg.color, height: `${hPct}%` }}
                  aria-label={`${b.label}: ${seg.value}`}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="flex justify-between font-mono text-[9px] text-patina tracking-[0.05em]">
        {bars.map((b) => (
          <span key={b.label} className="flex-1 text-center uppercase">
            {b.label}
          </span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create `web/components/charts/tokens-cost-chart.tsx`**

```tsx
/** Dual-axis chart: stacked bars (input / output tokens) on left axis,
 *  cost line on right axis. `buckets.length` must match. */
export type TokensCostBucket = {
  label: string;
  input_tokens: number;
  output_tokens: number;
  cost: number;
};

export function TokensCostChart({
  buckets,
  height = 150,
}: {
  buckets: TokensCostBucket[];
  height?: number;
}) {
  const maxTokens = Math.max(
    1,
    ...buckets.map((b) => b.input_tokens + b.output_tokens),
  );
  const maxCost = Math.max(0.0001, ...buckets.map((b) => b.cost));

  const vw = 240;
  const vh = 130;
  const barW = buckets.length ? Math.max(2, (vw / buckets.length) - 2) : 0;
  const gap = 2;

  const costPoints = buckets
    .map((b, i) => {
      const x = i * (vw / buckets.length) + barW / 2;
      const y = vh - (b.cost / maxCost) * (vh - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="relative" style={{ height }}>
      <div className="absolute left-0 top-0 bottom-[18px] w-[48px] flex flex-col justify-between font-mono text-[9px] text-aether-teal text-right pr-[6px]">
        <span>{(maxTokens / 1000).toFixed(0)}k</span>
        <span>{(maxTokens * 0.5 / 1000).toFixed(0)}k</span>
        <span>0</span>
      </div>
      <div className="absolute right-0 top-0 bottom-[18px] w-[40px] flex flex-col justify-between font-mono text-[9px] text-peach-neon text-left pl-[6px]">
        <span>${maxCost.toFixed(2)}</span>
        <span>${(maxCost / 2).toFixed(2)}</span>
        <span>$0</span>
      </div>
      <div className="absolute left-[48px] right-[40px] top-0 bottom-[18px] border-l border-r border-b border-[color:var(--border)]">
        <svg viewBox={`0 0 ${vw} ${vh}`} preserveAspectRatio="none" className="w-full h-full">
          {buckets.map((b, i) => {
            const x = i * (vw / buckets.length) + gap;
            const totalH = ((b.input_tokens + b.output_tokens) / maxTokens) * vh;
            const inputH = (b.input_tokens / maxTokens) * vh;
            const outputH = totalH - inputH;
            return (
              <g key={i}>
                <rect
                  x={x}
                  y={vh - totalH}
                  width={barW - gap}
                  height={outputH}
                  fill="#6BBAB1"
                  opacity={0.45}
                />
                <rect
                  x={x}
                  y={vh - inputH}
                  width={barW - gap}
                  height={inputH}
                  fill="#6BBAB1"
                  opacity={0.85}
                />
              </g>
            );
          })}
          {buckets.length > 1 ? (
            <polyline
              points={costPoints}
              fill="none"
              stroke="#E8A87C"
              strokeWidth={1.5}
            />
          ) : null}
        </svg>
      </div>
      <div className="absolute left-[48px] right-[40px] bottom-0 flex justify-between font-mono text-[9px] text-patina">
        {buckets.map((b, i) => (
          <span key={`${b.label}-${i}`}>{b.label}</span>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Type-check + commit**

```bash
cd /Users/andrewlavoie/code/langperf/web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/components/charts/
git commit -m "web: chart primitives — Sparkline, LineChart, StackedBarChart, TokensCostChart"
```

---

### Task 5: Dashboard composition components

**Files:**
- Create: `web/components/dashboard/kpi-strip.tsx`
- Create: `web/components/dashboard/agent-grid.tsx`
- Create: `web/components/dashboard/top-tools.tsx`
- Create: `web/components/dashboard/recent-flagged.tsx`
- Create: `web/components/dashboard/tool-agent-heatmap.tsx`
- Create: `web/components/dashboard/env-split.tsx`
- Create: `web/components/agent/time-range-picker.tsx`

- [ ] **Step 1: Create `web/components/agent/time-range-picker.tsx`**

```tsx
"use client";

import { useRouter, useSearchParams, usePathname } from "next/navigation";
import type { TimeWindow } from "@/lib/api";

const OPTIONS: TimeWindow[] = ["24h", "7d", "30d"];

export function TimeRangePicker({ current }: { current: TimeWindow }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const set = (w: TimeWindow) => {
    const next = new URLSearchParams(params.toString());
    next.set("window", w);
    router.push(`${pathname}?${next.toString()}`);
  };

  return (
    <span className="inline-flex border border-[color:var(--border-strong)] rounded-[3px] overflow-hidden">
      {OPTIONS.map((w) => {
        const on = w === current;
        return (
          <button
            key={w}
            type="button"
            onClick={() => set(w)}
            className={`px-[10px] py-[4px] text-[10px] font-mono uppercase tracking-[0.08em] border-r last:border-r-0 border-[color:var(--border)] ${
              on ? "bg-[color:rgba(107,186,177,0.08)] text-aether-teal" : "text-patina hover:text-warm-fog"
            }`}
          >
            {w}
          </button>
        );
      })}
    </span>
  );
}
```

- [ ] **Step 2: Create `web/components/dashboard/kpi-strip.tsx`**

```tsx
import type { OverviewKpi } from "@/lib/api";
import { fmtDuration } from "@/lib/format";

function Tile({ label, value, sub, accent = false, warn = false }: {
  label: string;
  value: string;
  sub?: string;
  accent?: boolean;
  warn?: boolean;
}) {
  const color = warn ? "text-warn" : accent ? "text-peach-neon" : "text-warm-fog";
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[6px]">
        {label}
      </div>
      <div className={`font-mono text-[20px] tracking-[-0.02em] ${color}`}>{value}</div>
      {sub ? (
        <div className="font-mono text-[10px] text-patina mt-[3px]">{sub}</div>
      ) : null}
    </div>
  );
}

function fmtPct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

function fmtLatency(ms: number | null): string {
  return ms == null ? "—" : fmtDuration(ms);
}

export function KpiStrip({ kpi, window }: { kpi: OverviewKpi; window: string }) {
  return (
    <div className="grid grid-cols-5 gap-[8px] mb-[10px]">
      <Tile label={`runs · ${window}`} value={kpi.runs.toLocaleString()} />
      <Tile label="agents" value={String(kpi.agents)} />
      <Tile
        label="error rate"
        value={fmtPct(kpi.error_rate)}
        warn={kpi.error_rate > 0.05}
        accent={kpi.error_rate > 0 && kpi.error_rate <= 0.05}
      />
      <Tile label="p95 latency" value={fmtLatency(kpi.p95_latency_ms)} />
      <Tile
        label="flagged"
        value={String(kpi.flagged)}
        accent={kpi.flagged > 0}
      />
    </div>
  );
}
```

- [ ] **Step 3: Create `web/components/dashboard/agent-grid.tsx`**

```tsx
import Link from "next/link";
import type { AgentSummaryWithMetrics } from "@/lib/api";
import { Sparkline } from "@/components/charts/sparkline";
import { fmtDuration } from "@/lib/format";

function statusDot(errorRate: number): string {
  if (errorRate === 0) return "#6BBAB1";       // ok — teal
  if (errorRate < 0.05) return "#E8A87C";      // noted — peach
  return "#D98A6A";                             // warn — deeper peach
}

export function AgentGrid({ agents }: { agents: AgentSummaryWithMetrics[] }) {
  if (agents.length === 0) {
    return (
      <div className="text-patina text-[12px] py-[24px]">No agents yet.</div>
    );
  }
  return (
    <div className="grid grid-cols-4 gap-[8px]">
      {agents.map((a) => {
        const errPct = (a.metrics.error_rate * 100).toFixed(1);
        const dot = statusDot(a.metrics.error_rate);
        return (
          <Link
            key={a.id}
            href={`/agents/${encodeURIComponent(a.name)}`}
            className="block border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[10px] hover:border-[color:var(--border-strong)]"
          >
            <div className="flex items-center gap-[6px] text-[12px] font-medium">
              <span style={{ background: dot, width: 6, height: 6 }} />
              <span className="truncate">{a.display_name ?? a.name}</span>
              <span className="ml-auto font-mono text-[9px] text-patina">
                v{a.version_count || 0}
              </span>
            </div>
            <div className="font-mono text-[10px] text-patina mt-[2px]">
              {a.metrics.runs.toLocaleString()} · {errPct}% err · p95{" "}
              {a.metrics.p95_latency_ms != null
                ? fmtDuration(a.metrics.p95_latency_ms)
                : "—"}
            </div>
            <Sparkline values={a.sparkline} stroke={dot} />
          </Link>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Create `web/components/dashboard/top-tools.tsx`**

```tsx
import type { TopTool } from "@/lib/api";

export function TopTools({ tools }: { tools: TopTool[] }) {
  const max = Math.max(1, ...tools.map((t) => t.calls));
  return (
    <div>
      {tools.length === 0 ? (
        <div className="text-patina text-[12px] py-[12px]">No tool calls in range.</div>
      ) : (
        tools.map((t) => {
          const pct = (t.calls / max) * 100;
          const errPct = t.calls ? (t.errors / t.calls) * 100 : 0;
          const warn = errPct > 2;
          return (
            <div
              key={t.tool}
              className="flex items-center py-[5px] text-[12px] border-b border-[color:var(--border)] last:border-b-0"
            >
              <span className="font-mono flex-1 truncate">{t.tool}</span>
              <div className="w-[100px] h-[4px] bg-[color:rgba(122,139,142,0.15)] mx-[10px] overflow-hidden">
                <div
                  className="h-full"
                  style={{
                    width: `${pct}%`,
                    background: warn ? "#E8A87C" : "#6BBAB1",
                  }}
                />
              </div>
              <span className="font-mono text-[10px] text-patina min-w-[74px] text-right tabular-nums">
                {t.calls.toLocaleString()}
                {t.errors > 0 ? (
                  <span className="text-warn ml-[4px]">{errPct.toFixed(1)}%e</span>
                ) : null}
              </span>
            </div>
          );
        })
      )}
    </div>
  );
}
```

- [ ] **Step 5: Create `web/components/dashboard/recent-flagged.tsx`**

```tsx
import Link from "next/link";
import type { FlaggedRun } from "@/lib/api";
import { ClientTime } from "@/components/client-time";

function tagCls(tag: string | null): string {
  if (tag === "bad") return "text-warn border-[color:rgba(217,138,106,0.4)]";
  if (tag === "interesting" || tag === "todo")
    return "text-peach-neon border-[color:rgba(232,168,124,0.4)]";
  if (tag === "good") return "text-aether-teal border-[color:rgba(107,186,177,0.35)]";
  return "text-patina border-[color:var(--border-strong)]";
}

export function RecentFlagged({ rows }: { rows: FlaggedRun[] }) {
  if (rows.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No flagged runs in range.</div>;
  }
  return (
    <div>
      {rows.map((r) => (
        <Link
          key={r.id}
          href={`/r/${r.id}`}
          className="grid grid-cols-[60px_1fr_70px_80px] gap-[10px] items-center py-[6px] border-b border-[color:var(--border)] last:border-b-0 text-[12px] hover:bg-[color:rgba(107,186,177,0.03)]"
        >
          <span className="font-mono text-[10px] text-patina">{r.id.slice(0, 6)}</span>
          <span className="truncate">
            {r.agent_name ? (
              <span className="text-warm-fog">{r.agent_name}</span>
            ) : null}
            {r.summary ? (
              <span className="text-patina"> · {r.summary}</span>
            ) : null}
          </span>
          <span
            className={`font-mono text-[9px] uppercase tracking-[0.08em] border px-[6px] py-[2px] text-center ${tagCls(r.status_tag)}`}
          >
            {r.status_tag ?? "—"}
          </span>
          <span className="font-mono text-[10px] text-patina text-right">
            <ClientTime iso={r.started_at} />
          </span>
        </Link>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Create `web/components/dashboard/tool-agent-heatmap.tsx`**

```tsx
import type { HeatmapCell } from "@/lib/api";

export function ToolAgentHeatmap({ cells }: { cells: HeatmapCell[] }) {
  if (cells.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No data.</div>;
  }

  const agents = Array.from(new Set(cells.map((c) => c.agent_name)));
  const tools = Array.from(new Set(cells.map((c) => c.tool)));
  const map = new Map<string, number>();
  let max = 1;
  for (const c of cells) {
    map.set(`${c.agent_name}|${c.tool}`, c.calls);
    if (c.calls > max) max = c.calls;
  }

  const cellBg = (n: number | undefined): string => {
    if (n == null) return "rgba(122,139,142,0.08)";
    const alpha = Math.min(1, 0.18 + (n / max) * 0.8);
    return `rgba(107,186,177,${alpha.toFixed(2)})`;
  };

  const fmt = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));

  return (
    <div
      className="grid gap-[2px] text-[10px] font-mono"
      style={{
        gridTemplateColumns: `140px repeat(${tools.length}, 1fr)`,
      }}
    >
      <div />
      {tools.map((t) => (
        <div key={t} className="text-center text-patina truncate py-[4px]">
          {t.replace(/_/g, " ").slice(0, 10)}
        </div>
      ))}

      {agents.map((a) => (
        <>
          <div key={`${a}-lbl`} className="text-patina px-[6px] py-[4px] truncate">
            {a}
          </div>
          {tools.map((t) => {
            const n = map.get(`${a}|${t}`);
            return (
              <div
                key={`${a}-${t}`}
                className="h-[22px] flex items-center justify-center"
                style={{ background: cellBg(n), color: n != null ? "#181D21" : "#7A8B8E" }}
              >
                {n != null ? fmt(n) : "—"}
              </div>
            );
          })}
        </>
      ))}
    </div>
  );
}
```

- [ ] **Step 7: Create `web/components/dashboard/env-split.tsx`**

```tsx
import type { EnvSplit } from "@/lib/api";

const COLORS: Record<string, string> = {
  prod: "#6BBAB1",
  staging: "#E8A87C",
  dev: "#7A8B8E",
};

export function EnvSplitCard({ entries }: { entries: EnvSplit[] }) {
  const total = entries.reduce((s, e) => s + e.runs, 0) || 1;
  return (
    <>
      <div className="flex h-[22px] rounded-[2px] overflow-hidden my-[6px] mb-[10px]">
        {entries.map((e) => {
          const pct = (e.runs / total) * 100;
          return (
            <div
              key={e.environment}
              style={{ width: `${pct}%`, background: COLORS[e.environment] ?? "#3A4950" }}
              title={`${e.environment}: ${e.runs}`}
            />
          );
        })}
      </div>
      <div className="font-mono text-[10px] text-patina leading-[1.8]">
        {entries.map((e) => {
          const pct = ((e.runs / total) * 100).toFixed(0);
          const dot = COLORS[e.environment] ?? "#3A4950";
          return (
            <div key={e.environment}>
              <span
                style={{ background: dot, width: 6, height: 6, display: "inline-block", marginRight: 6 }}
              />
              {e.environment} <b className="text-warm-fog font-medium">{pct}%</b> ·{" "}
              {e.runs.toLocaleString()}
            </div>
          );
        })}
      </div>
    </>
  );
}
```

- [ ] **Step 8: Type-check + commit**

```bash
cd /Users/andrewlavoie/code/langperf/web && npx tsc --noEmit
cd /Users/andrewlavoie/code/langperf
git add web/components/agent/time-range-picker.tsx web/components/dashboard/
git commit -m "web: Dashboard composition components + time-range picker"
```

---

### Task 6: Real Dashboard (`/` page)

**Files:**
- Modify: `web/app/page.tsx` — replace placeholder with real composition

- [ ] **Step 1: Replace `web/app/page.tsx` with this content**

```tsx
import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import {
  getOverview,
  listAgents,
  type AgentSummaryWithMetrics,
  type OverviewResponse,
  type TimeWindow,
} from "@/lib/api";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { AgentGrid } from "@/components/dashboard/agent-grid";
import { TopTools } from "@/components/dashboard/top-tools";
import { RecentFlagged } from "@/components/dashboard/recent-flagged";
import { ToolAgentHeatmap } from "@/components/dashboard/tool-agent-heatmap";
import { EnvSplitCard } from "@/components/dashboard/env-split";
import { StackedBarChart } from "@/components/charts/bar-chart";
import { LineChart } from "@/components/charts/line-chart";
import { TimeRangePicker } from "@/components/agent/time-range-picker";

export const dynamic = "force-dynamic";

function Card({
  title,
  right,
  children,
}: {
  title?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[12px]">
      {title ? (
        <div className="flex items-center justify-between mb-[8px]">
          <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
            {title}
          </span>
          {right ? (
            <span className="font-mono text-[10px] text-aether-teal">{right}</span>
          ) : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}

function V2Card({ label, body }: { label: string; body: string }) {
  return (
    <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
        v2
      </div>
      <div className="text-[12px] text-warm-fog font-medium mb-[2px]">{label}</div>
      <div className="text-[11px] text-patina leading-[1.5]">{body}</div>
    </div>
  );
}

function parseWindow(v: string | undefined): TimeWindow {
  if (v === "24h" || v === "30d") return v;
  return "7d";
}

export default async function Dashboard({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const window = parseWindow(params.window);

  let overview: OverviewResponse;
  let agents: AgentSummaryWithMetrics[];
  try {
    const [ov, ag] = await Promise.all([
      getOverview(window),
      listAgents({ with_metrics: true, window }),
    ]);
    overview = ov;
    agents = ag as AgentSummaryWithMetrics[];
  } catch (err) {
    return (
      <AppShell
        topBar={{
          breadcrumb: (
            <span className="font-medium text-warm-fog">Dashboard</span>
          ),
        }}
      >
        <div
          className="rounded border p-4 text-sm"
          style={{
            borderColor: "rgba(217,138,106,0.45)",
            background: "rgba(217,138,106,0.1)",
          }}
        >
          <p className="font-medium text-warn">Could not reach langperf-api</p>
          <p className="mt-1 text-patina font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </AppShell>
    );
  }

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Pinned agents</CtxHeader>
      {agents.slice(0, 6).map((a) => (
        <CtxItem key={a.id} sub={a.metrics.runs.toLocaleString()}>
          <Link href={`/agents/${encodeURIComponent(a.name)}`} className="hover:underline">
            {a.display_name ?? a.name}
          </Link>
        </CtxItem>
      ))}
      <CtxHeader>Saved views</CtxHeader>
      <CtxItem>(Phase 4)</CtxItem>
    </ContextSidebar>
  );

  // Volume chart
  const volumeBars = overview.volume_by_day.map((d) => {
    const date = new Date(d.day);
    const label = date.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
    return {
      label,
      segments: [
        { color: "#6BBAB1", value: d.prod },
        { color: "#E8A87C", value: d.staging },
        { color: "#7A8B8E", value: d.dev + d.other },
      ],
    };
  });

  // Latency chart data — show flat current p50/p95/p99 across window as a single
  // horizontal line each (real per-bucket series requires a follow-up endpoint).
  const flat = (v: number | null) => (v == null ? [] : Array(7).fill(v));
  const latencyTicks = (() => {
    const p99 = overview.kpi.p99_latency_ms ?? 1000;
    const rounded = Math.ceil(p99 / 1000) * 1000;
    const step = rounded / 4;
    return [0, step, step * 2, step * 3, step * 4];
  })();

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Dashboard</span>,
        right: (
          <>
            <TimeRangePicker current={window} />
            <Chip variant="primary">ingest ok</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <KpiStrip kpi={overview.kpi} window={window} />

      <div className="grid grid-cols-[2fr_1fr] gap-[8px] mb-[10px]">
        <Card title={`Run volume · ${window} · by env`}>
          <StackedBarChart bars={volumeBars} />
        </Card>
        <Card title={`Latency · p50/p95/p99 · ${window}`}>
          <LineChart
            lines={[
              { name: "p50", color: "#E8A87C", values: flat(overview.kpi.p50_latency_ms) },
              { name: "p95", color: "#6BBAB1", values: flat(overview.kpi.p95_latency_ms) },
              { name: "p99", color: "#D98A6A", values: flat(overview.kpi.p99_latency_ms) },
            ]}
            xLabels={["start", "", "", "", "now"]}
            yTicks={latencyTicks}
            yFormat={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`)}
          />
        </Card>
      </div>

      <div className="grid grid-cols-[1.2fr_1fr_0.8fr] gap-[8px] mb-[10px]">
        <Card title={`Top tools · ${window}`} right="across all agents">
          <TopTools tools={overview.top_tools} />
        </Card>
        <Card title="Tool-by-agent heatmap">
          <ToolAgentHeatmap cells={overview.heatmap} />
        </Card>
        <Card title="Env split">
          <EnvSplitCard entries={overview.env_split} />
        </Card>
      </div>

      <Card title="Your agents">
        <AgentGrid agents={agents} />
      </Card>

      <div className="h-[10px]" />

      <Card title="Recent flagged" right={<Link href="/history">view history →</Link>}>
        <RecentFlagged rows={overview.recent_flagged} />
      </Card>

      <div className="h-[10px]" />

      <div className="grid grid-cols-3 gap-[8px]">
        <V2Card
          label="Triage queue"
          body="Priority-ordered runs needing review. Clustered failures across agents."
        />
        <V2Card
          label="Eval regressions"
          body="Which prompts/tools regressed against your eval set this week."
        />
        <V2Card
          label="Training data export"
          body="Flagged + corrected runs as SFT/DPO jsonl from this surface."
        />
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd /Users/andrewlavoie/code/langperf/web && npx tsc --noEmit
```

- [ ] **Step 3: Browser verify**

```bash
cd /Users/andrewlavoie/code/langperf
docker compose restart langperf-web
sleep 4
```

Open `http://localhost:3030/` — expected:
- KPI strip shows real numbers (runs > 0, at least 1 agent)
- Run volume chart has bars
- Latency chart shows p50/p95/p99 horizontal lines
- Top tools list has entries
- Heatmap shows cells
- Agent grid has cards with sparklines
- Recent flagged table either has rows or shows "No flagged runs in range."
- Clicking an agent card goes to `/agents/<name>` (which redirects to overview — placeholder still until Task 8)
- Time-range chip toggling updates the URL and re-fetches (via server component)

- [ ] **Step 4: Commit**

```bash
git add web/app/page.tsx
git commit -m "web: real Dashboard consuming /api/overview + /api/agents"
```

---

### Task 7: Real Agents index (`/agents` page)

**Files:**
- Modify: `web/app/agents/page.tsx` — replace placeholder

- [ ] **Step 1: Replace `web/app/agents/page.tsx` with**

```tsx
import Link from "next/link";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import { listAgents, type AgentSummaryWithMetrics, type TimeWindow } from "@/lib/api";
import { AgentGrid } from "@/components/dashboard/agent-grid";
import { TimeRangePicker } from "@/components/agent/time-range-picker";

export const dynamic = "force-dynamic";

function parseWindow(v: string | undefined): TimeWindow {
  if (v === "24h" || v === "30d") return v;
  return "7d";
}

export default async function AgentsIndex({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const window = parseWindow(params.window);

  let agents: AgentSummaryWithMetrics[];
  try {
    agents = (await listAgents({ with_metrics: true, window })) as AgentSummaryWithMetrics[];
  } catch (err) {
    return (
      <AppShell
        topBar={{
          breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        }}
      >
        <div
          className="rounded border p-4 text-sm"
          style={{
            borderColor: "rgba(217,138,106,0.45)",
            background: "rgba(217,138,106,0.1)",
          }}
        >
          <p className="font-medium text-warn">Could not reach langperf-api</p>
          <p className="mt-1 text-patina font-mono text-xs">
            {err instanceof Error ? err.message : String(err)}
          </p>
        </div>
      </AppShell>
    );
  }

  const sidebar = (
    <ContextSidebar>
      <CtxHeader action="+ new">Agents</CtxHeader>
      {agents.map((a) => (
        <CtxItem key={a.id} sub={a.metrics.runs.toLocaleString()}>
          <Link
            href={`/agents/${encodeURIComponent(a.name)}`}
            className="hover:underline"
          >
            {a.display_name ?? a.name}
          </Link>
        </CtxItem>
      ))}
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb: <span className="font-medium text-warm-fog">Agents</span>,
        right: (
          <>
            <TimeRangePicker current={window} />
            <Chip>env: all</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <AgentGrid agents={agents} />
    </AppShell>
  );
}
```

- [ ] **Step 2: Type-check + browser verify**

```bash
cd /Users/andrewlavoie/code/langperf/web && npx tsc --noEmit
```

Open `http://localhost:3030/agents` — expected: grid of agent cards with sparklines, sidebar lists all agents with run counts.

- [ ] **Step 3: Commit**

```bash
git add web/app/agents/page.tsx
git commit -m "web: real Agents index with metric-enriched cards"
```

---

### Task 8: Real Agent-detail Overview tab

**Files:**
- Create: `web/components/agent/identity-strip.tsx`
- Create: `web/components/agent/runs-table.tsx`
- Modify: `web/app/agents/[name]/[tab]/page.tsx` — Overview tab consumes real data

- [ ] **Step 1: Create `web/components/agent/identity-strip.tsx`**

```tsx
import { Chip } from "@/components/ui/chip";
import { fmtDuration } from "@/lib/format";
import { ClientTime } from "@/components/client-time";
import type { AgentDetail, AgentMetrics } from "@/lib/api";

export function IdentityStrip({
  agent,
  version,
  env,
  metrics,
  lastRunAt,
}: {
  agent: AgentDetail;
  version: string | null;
  env: string | null;
  metrics: AgentMetrics | null;
  lastRunAt: string | null;
}) {
  return (
    <div className="flex items-center gap-2 px-[14px] py-[9px] -mx-[14px] -mt-[14px] mb-[14px] border-b border-[color:var(--border)] bg-gradient-to-b from-[color:var(--surface-2)] to-[color:var(--background)]">
      <Label>Agent</Label>
      <Chip>{agent.display_name ?? agent.name}</Chip>
      <Label className="ml-[6px]">Ver</Label>
      <Chip>{version ?? "—"}</Chip>
      <Label className="ml-[6px]">Env</Label>
      <Chip>{env ?? "—"}</Chip>
      <div className="flex-1" />
      <span className="font-mono text-[10px] text-patina">
        {lastRunAt ? (
          <>
            last run <b className="text-warm-fog font-medium"><ClientTime iso={lastRunAt} /></b> ·{" "}
          </>
        ) : null}
        {metrics ? (
          <>
            <b className="text-warm-fog font-medium">{metrics.runs.toLocaleString()}</b>/{metrics.window} ·{" "}
            {metrics.p50_latency_ms != null ? (
              <>p50 <b className="text-warm-fog font-medium">{fmtDuration(metrics.p50_latency_ms)}</b> · </>
            ) : null}
            {metrics.p95_latency_ms != null ? (
              <>p95 <b className="text-warm-fog font-medium">{fmtDuration(metrics.p95_latency_ms)}</b> · </>
            ) : null}
            err <b className="text-warn font-medium">{(metrics.error_rate * 100).toFixed(1)}%</b>
          </>
        ) : null}
      </span>
    </div>
  );
}

function Label({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={`font-mono text-[9px] text-patina uppercase tracking-[0.1em] mr-[2px] ${className}`}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 2: Create `web/components/agent/runs-table.tsx`**

```tsx
import Link from "next/link";
import type { AgentRunRow } from "@/lib/api";
import { fmtDuration } from "@/lib/format";
import { ClientTime } from "@/components/client-time";

function tagCls(tag: string | null): string {
  if (tag === "bad") return "text-warn border-[color:rgba(217,138,106,0.4)]";
  if (tag === "interesting" || tag === "todo")
    return "text-peach-neon border-[color:rgba(232,168,124,0.4)]";
  if (tag === "good") return "text-aether-teal border-[color:rgba(107,186,177,0.35)]";
  return "text-patina border-[color:var(--border-strong)]";
}

export function RunsTable({ rows }: { rows: AgentRunRow[] }) {
  if (rows.length === 0) {
    return <div className="text-patina text-[12px] p-[16px]">No runs.</div>;
  }
  return (
    <table className="w-full border-collapse text-[12px]">
      <thead>
        <tr>
          <Th>Time</Th>
          <Th>ID</Th>
          <Th>Input</Th>
          <Th className="text-right">Steps</Th>
          <Th className="text-right">Tokens</Th>
          <Th className="text-right">Latency</Th>
          <Th>Ver</Th>
          <Th>Env</Th>
          <Th>Status</Th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr
            key={r.id}
            className="border-b border-[color:var(--border)] last:border-b-0 hover:bg-[color:rgba(107,186,177,0.03)]"
          >
            <Td mono>
              <ClientTime iso={r.started_at} />
            </Td>
            <Td mono>
              <Link href={`/r/${r.id}`} className="text-aether-teal hover:underline">
                {r.id.slice(0, 6)}
              </Link>
            </Td>
            <Td>
              <span className="truncate inline-block max-w-[360px] align-bottom">
                {r.name ?? <em className="text-patina">(unnamed)</em>}
              </span>
            </Td>
            <Td mono className="text-right">
              <b className="text-warm-fog">{r.step_count}</b>
            </Td>
            <Td mono className="text-right">
              <b className="text-warm-fog">{r.token_count.toLocaleString()}</b>
            </Td>
            <Td mono className="text-right">
              <b className="text-warm-fog">
                {r.duration_ms != null ? fmtDuration(r.duration_ms) : "—"}
              </b>
            </Td>
            <Td mono>{r.version_label ?? "—"}</Td>
            <Td mono>{r.environment ?? "—"}</Td>
            <Td>
              <span
                className={`inline-block font-mono text-[9px] uppercase tracking-[0.08em] border px-[6px] py-[2px] ${tagCls(r.status_tag)}`}
              >
                {r.status_tag ?? "—"}
              </span>
            </Td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`text-left font-mono text-[9px] text-patina uppercase tracking-[0.1em] px-[10px] py-[8px] border-b border-[color:var(--border)] font-medium ${className}`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  mono = false,
  className = "",
}: {
  children: React.ReactNode;
  mono?: boolean;
  className?: string;
}) {
  return (
    <td
      className={`px-[10px] py-[7px] text-warm-fog ${
        mono ? "font-mono text-[11px] text-patina" : ""
      } ${className}`}
    >
      {children}
    </td>
  );
}
```

- [ ] **Step 3: Replace `web/app/agents/[name]/[tab]/page.tsx`**

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import {
  ContextSidebar,
  CtxHeader,
  CtxItem,
} from "@/components/shell/context-sidebar";
import { Chip } from "@/components/ui/chip";
import {
  getAgent,
  getAgentMetrics,
  getAgentRuns,
  getAgentTools,
  type AgentDetail,
  type AgentMetrics,
  type AgentRunsResponse,
  type AgentToolUsage,
  type TimeWindow,
} from "@/lib/api";
import { IdentityStrip } from "@/components/agent/identity-strip";
import { RunsTable } from "@/components/agent/runs-table";
import { TopTools } from "@/components/dashboard/top-tools";
import { TokensCostChart } from "@/components/charts/tokens-cost-chart";
import { LineChart } from "@/components/charts/line-chart";
import { StackedBarChart } from "@/components/charts/bar-chart";
import { TimeRangePicker } from "@/components/agent/time-range-picker";

export const dynamic = "force-dynamic";

const TABS = ["overview", "runs", "prompt", "tools", "versions", "config"] as const;
type Tab = (typeof TABS)[number];

function parseWindow(v: string | undefined): TimeWindow {
  if (v === "24h" || v === "30d") return v;
  return "7d";
}

function Card({
  title,
  right,
  children,
  className = "",
}: {
  title?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[12px] ${className}`}>
      {title ? (
        <div className="flex items-center justify-between mb-[8px]">
          <span className="font-mono text-[9px] text-patina uppercase tracking-[0.1em]">
            {title}
          </span>
          {right ? (
            <span className="font-mono text-[10px] text-aether-teal">{right}</span>
          ) : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}

function V2Card({ label, body }: { label: string; body: string }) {
  return (
    <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
        v2
      </div>
      <div className="text-[12px] text-warm-fog font-medium mb-[2px]">{label}</div>
      <div className="text-[11px] text-patina leading-[1.5]">{body}</div>
    </div>
  );
}

function PlaceholderTab({ name, tab }: { name: string; tab: string }) {
  return (
    <div className="border border-[color:var(--border)] border-l-2 border-l-peach-neon rounded-[3px] bg-[color:var(--surface)] p-[14px]">
      <div className="font-mono text-[9px] text-peach-neon uppercase tracking-[0.1em] mb-[4px]">
        follow-up · {tab}
      </div>
      <div className="text-[13px] text-warm-fog">
        This tab's content lands in a follow-up spec. Overview (the current
        tab) is live — metrics, charts, and run history for {name}.
      </div>
    </div>
  );
}

export default async function AgentTab({
  params,
  searchParams,
}: {
  params: Promise<{ name: string; tab: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { name, tab } = await params;
  if (!TABS.includes(tab as Tab)) notFound();
  const sp = await searchParams;
  const window = parseWindow(sp.window);

  let agent: AgentDetail;
  try {
    agent = await getAgent(name);
  } catch (err) {
    notFound();
  }

  let metrics: AgentMetrics | null = null;
  let tools: AgentToolUsage[] = [];
  let runs: AgentRunsResponse | null = null;
  if (tab === "overview") {
    try {
      const [m, t, r] = await Promise.all([
        getAgentMetrics(name, window),
        getAgentTools(name, window),
        getAgentRuns(name, { limit: 10 }),
      ]);
      metrics = m;
      tools = t;
      runs = r;
    } catch {
      // leave nulls; the page will render empty states
    }
  }

  const breadcrumb = (
    <>
      <Link href="/agents" className="hover:text-warm-fog">
        Agents
      </Link>
      <span className="mx-[6px] text-[color:var(--border-strong)]">›</span>
      <span className="font-medium text-warm-fog">{name}</span>
    </>
  );

  const latestVersion = agent.versions[0]?.label ?? null;
  const env = runs?.items[0]?.environment ?? null;
  const lastRunAt = runs?.items[0]?.started_at ?? null;

  const sidebar = (
    <ContextSidebar>
      <CtxHeader>Versions</CtxHeader>
      {agent.versions.length === 0 ? (
        <CtxItem>(none)</CtxItem>
      ) : (
        agent.versions.slice(0, 8).map((v, i) => (
          <CtxItem key={v.id} active={i === 0}>
            {v.label}
          </CtxItem>
        ))
      )}
      <CtxHeader>Environments</CtxHeader>
      {(runs?.items ?? [])
        .map((r) => r.environment)
        .filter((e, i, arr): e is string => !!e && arr.indexOf(e) === i)
        .slice(0, 8)
        .map((e) => (
          <CtxItem key={e}>{e}</CtxItem>
        ))}
      <CtxHeader>Saved filters</CtxHeader>
      <CtxItem>(Phase 4)</CtxItem>
    </ContextSidebar>
  );

  return (
    <AppShell
      topBar={{
        breadcrumb,
        right: (
          <>
            <TimeRangePicker current={window} />
            <Chip>env: {env ?? "all"}</Chip>
          </>
        ),
      }}
      contextSidebar={sidebar}
    >
      <IdentityStrip
        agent={agent}
        version={latestVersion}
        env={env}
        metrics={metrics}
        lastRunAt={lastRunAt}
      />

      <div className="flex gap-[20px] border-b border-[color:var(--border)] -mx-[14px] px-[14px] mb-[14px]">
        {TABS.map((t) => {
          const active = t === tab;
          return (
            <Link
              key={t}
              href={`/agents/${encodeURIComponent(name)}/${t}`}
              className={`py-[10px] text-[12px] -mb-px border-b-2 ${
                active
                  ? "text-warm-fog border-b-aether-teal"
                  : "text-patina border-b-transparent hover:text-warm-fog"
              }`}
            >
              <span className="capitalize">{t}</span>
            </Link>
          );
        })}
      </div>

      {tab !== "overview" ? (
        <PlaceholderTab name={name} tab={tab} />
      ) : (
        <>
          {/* KPI strip agent-scoped */}
          <div className="grid grid-cols-5 gap-[8px] mb-[10px]">
            <KpiTile
              label={`runs · ${window}`}
              value={metrics ? metrics.runs.toLocaleString() : "—"}
            />
            <KpiTile
              label="error rate"
              value={metrics ? `${(metrics.error_rate * 100).toFixed(1)}%` : "—"}
              accent={metrics != null && metrics.error_rate > 0}
              warn={metrics != null && metrics.error_rate > 0.05}
            />
            <KpiTile
              label="p95 latency"
              value={metrics?.p95_latency_ms != null ? `${metrics.p95_latency_ms}ms` : "—"}
            />
            <KpiTile label="tools called" value={String(tools.length)} />
            <KpiTile
              label="total tokens"
              value={metrics ? metrics.total_tokens.toLocaleString() : "—"}
            />
          </div>

          {/* Row 1: run volume + latency */}
          <div className="grid grid-cols-2 gap-[8px] mb-[10px]">
            <Card title={`Run volume · ${window}`}>
              <SimpleVolume runs={runs?.items ?? []} window={window} />
            </Card>
            <Card title={`Latency · p50/p95/p99 · ${window}`}>
              <LineChart
                lines={[
                  { name: "p50", color: "#E8A87C", values: flat(metrics?.p50_latency_ms ?? null) },
                  { name: "p95", color: "#6BBAB1", values: flat(metrics?.p95_latency_ms ?? null) },
                  { name: "p99", color: "#D98A6A", values: flat(metrics?.p99_latency_ms ?? null) },
                ]}
                xLabels={["start", "", "", "", "now"]}
                yTicks={latencyTicks(metrics)}
                yFormat={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`)}
              />
            </Card>
          </div>

          {/* Row 2: tokens/cost + tools */}
          <div className="grid grid-cols-2 gap-[8px] mb-[10px]">
            <Card title={`Tokens & cost · ${window}`}>
              <TokensCostChart
                buckets={tokensCostFromRuns(runs?.items ?? [])}
              />
            </Card>
            <Card title={`Tools · ${window}`} right="defs →">
              <TopTools tools={tools} />
            </Card>
          </div>

          {/* Row 3: recent runs */}
          <Card title="Recent runs" className="!p-0">
            <RunsTable rows={runs?.items ?? []} />
          </Card>

          <div className="h-[10px]" />

          <div className="grid grid-cols-3 gap-[8px]">
            <V2Card
              label="Eval set · pass rate"
              body="Run a curated eval set against every new version. Gate prod promotion on pass rate."
            />
            <V2Card
              label="Comments & reviewers"
              body="SME notes on specific nodes. Assign flagged runs to reviewers."
            />
            <V2Card
              label="Replay against new prompt"
              body="Re-run a flagged trajectory against the next version to check if the issue was fixed."
            />
          </div>
        </>
      )}
    </AppShell>
  );
}

function KpiTile({
  label,
  value,
  accent = false,
  warn = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
  warn?: boolean;
}) {
  const color = warn ? "text-warn" : accent ? "text-peach-neon" : "text-warm-fog";
  return (
    <div className="border border-[color:var(--border)] rounded-[3px] bg-[color:var(--surface)] p-[10px]">
      <div className="font-mono text-[9px] text-patina uppercase tracking-[0.1em] mb-[6px]">
        {label}
      </div>
      <div className={`font-mono text-[20px] tracking-[-0.02em] ${color}`}>{value}</div>
    </div>
  );
}

function SimpleVolume({
  runs,
  window,
}: {
  runs: { started_at: string; version_label: string | null }[];
  window: TimeWindow;
}) {
  // Bucket by day; color-code by version label (first two versions teal/peach, rest patina).
  const buckets = new Map<string, Map<string, number>>();
  const versions = new Set<string>();
  for (const r of runs) {
    const day = r.started_at.slice(0, 10);
    const ver = r.version_label ?? "—";
    versions.add(ver);
    const inner = buckets.get(day) ?? new Map<string, number>();
    inner.set(ver, (inner.get(ver) ?? 0) + 1);
    buckets.set(day, inner);
  }
  const versionOrder = Array.from(versions).slice(0, 6);
  const colors = ["#6BBAB1", "#E8A87C", "#7A8B8E", "#D98A6A", "#3A4950", "#2E3A40"];
  const bars = Array.from(buckets.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([day, vers]) => {
      const label = new Date(day).toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
      return {
        label,
        segments: versionOrder.map((v, i) => ({
          color: colors[i] ?? "#3A4950",
          value: vers.get(v) ?? 0,
        })),
      };
    });
  if (bars.length === 0) {
    return <div className="text-patina text-[12px] py-[12px]">No data in {window}.</div>;
  }
  return <StackedBarChart bars={bars} />;
}

function flat(v: number | null): number[] {
  return v == null ? [] : [v, v, v, v, v, v, v];
}

function latencyTicks(m: AgentMetrics | null): number[] {
  const p99 = m?.p99_latency_ms ?? 1000;
  const rounded = Math.max(1000, Math.ceil(p99 / 1000) * 1000);
  const step = rounded / 4;
  return [0, step, step * 2, step * 3, step * 4];
}

function tokensCostFromRuns(
  runs: { started_at: string; token_count: number }[],
): { label: string; input_tokens: number; output_tokens: number; cost: number }[] {
  const buckets = new Map<string, number>();
  for (const r of runs) {
    const day = r.started_at.slice(0, 10);
    buckets.set(day, (buckets.get(day) ?? 0) + r.token_count);
  }
  return Array.from(buckets.entries())
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([day, total]) => {
      const label = new Date(day).toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
      // Assume ~80/20 input/output split and $0.00001 / token cost model until real cost ingest lands.
      const input_tokens = Math.round(total * 0.8);
      const output_tokens = total - input_tokens;
      const cost = total * 0.00001;
      return { label, input_tokens, output_tokens, cost };
    });
}
```

- [ ] **Step 4: Type-check + browser verify**

```bash
cd /Users/andrewlavoie/code/langperf/web && npx tsc --noEmit
```

Open `http://localhost:3030/agents/<any-agent-name>/overview` — expected: real identity strip, 5 KPI tiles, run volume chart (bars by day), p50/p95/p99 horizontal lines, tokens+cost chart, tools list, recent runs table with real rows, v2 teasers.

Click a different tab (runs/prompt/tools/versions/config) — see the "follow-up spec" placeholder.

- [ ] **Step 5: Commit**

```bash
git add web/components/agent/identity-strip.tsx web/components/agent/runs-table.tsx web/app/agents/[name]/[tab]/page.tsx
git commit -m "web: real Agent-detail Overview tab with KPIs, charts, tools, runs"
```

---

### Task 9: Integration pass

**Files:**
- None to modify; this task is verification.

- [ ] **Step 1: Full build**

```bash
cd /Users/andrewlavoie/code/langperf/web && npx next build
```

Expected: clean build, all routes present.

- [ ] **Step 2: Full route walk**

With `docker compose up` running, open each:
- `/` — dashboard with real data
- `/?window=24h` — re-renders with 24h scope
- `/agents` — grid of cards, click one →
- `/agents/<name>` → redirects to `/overview`
- `/agents/<name>/overview` — real Overview
- `/agents/<name>/runs` — placeholder
- `/agents/<name>/prompt` — placeholder
- `/history` — untouched (still uses FilterBar + trajectory list)
- `/logs` — untouched (still placeholder)
- `/settings/log-forwarding` — untouched (still placeholder)
- `/r/<id>` — redirects to `/t/<id>`
- `/t/<id>` — works as before

- [ ] **Step 3: Final commit + summary**

```bash
cd /Users/andrewlavoie/code/langperf
git commit --allow-empty -m "phase-2b: agent UI complete (dashboard + agents index + agent-detail overview)"
```

---

## Self-Review

**Spec coverage** against `docs/superpowers/specs/2026-04-17-ui-shell-and-agent-first-class-design.md`:

| Spec section | Covered by |
|---|---|
| §6.1 Dashboard — KPI strip, volume × time × env, error rate, top tools, latency, env split, agent grid, recent flagged, heatmap, v2 teasers | Tasks 1, 4, 5, 6 |
| §6.2 Agents index — card grid | Task 7 |
| §6.3 Agent detail Overview — identity strip, KPIs, run volume by version, latency p50/p95/p99 with x-axis, tokens+cost, per-agent tools, recent runs | Task 8 |
| §8.2 Extended `/api/agents?with_metrics=true` | Task 2 |
| §8.2 New `/api/overview` | Task 1 |

**Explicitly deferred:**
- Dashboard's latency chart shows flat lines (not per-bucket series) because the API returns window aggregates, not time-bucketed percentiles. Full time-series latency requires a follow-up endpoint (`/api/metrics/latency?bucket=1h`). Same applies to the agent-detail latency chart. Called out via the flat-lines pattern so it's visible to the user.
- `tokens-cost-chart` in Agent-detail uses an assumed 80/20 input/output split and a placeholder $0.00001/token cost, because real input/output token counts and cost aren't captured on `Trajectory` yet (only aggregate `token_count`). The chart renders something meaningful today and swaps to real data when the ingest adds per-message accounting.
- Run volume "by version" on agent detail relies on the last 10 runs (what's fetched for the table), not a full window query. Full-window stacked-by-version chart needs a new endpoint `/api/agents/{name}/volume?bucket=day&by=version`.

**Type consistency:**
- `AgentSummaryWithMetrics` defined identically in Task 2 (Python) and Task 3 (TS).
- `OverviewResponse` / `OverviewKpi` / `VolumeDay` / `EnvSplit` / `TopTool` / `FlaggedRun` / `HeatmapCell` shapes match across Python (Task 1) and TS (Task 3).
- Chart props (`LineSeries`, `BarColumn`, `BarSegment`, `TokensCostBucket`) only defined in web/ and consumed internally — no drift risk.

**Placeholder scan:** Tabs other than Overview still show a placeholder card in Task 8's page — that's intentional (spec defers Prompt/Tools/Versions/Config/Runs to later specs). All code blocks are complete.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-17-phase-2b-agent-ui.md`.

Same two execution options:

**1. Subagent-Driven (recommended)**
**2. Inline**

Which approach?
