"""Agents list / detail / PATCH endpoints.

Thin HTTP-adapter layer — all mutation / token / metrics logic lives in
`app.services.agents` and `app.services.agent_metrics`.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response as FastAPIResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.schemas import (
    AgentDetail,
    AgentMetrics,
    AgentPatch,
    AgentPromptRow,
    AgentRunsResponse,
    AgentSummary,
    AgentSummaryWithMetrics,
    AgentToolUsage,
)
from app.services import agent_failures
from app.services import agent_metrics as metrics_service
from app.services import agent_profile
from app.services import agent_timeseries
from app.services import agent_worklist
from app.services import agents as agents_service
from app.services.agents import AgentCreate

router = APIRouter(prefix="/api/agents")


@router.get(
    "",
    response_model=list[AgentSummary] | list[AgentSummaryWithMetrics],
)
async def list_agents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    with_metrics: bool = Query(default=False),
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    project: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
):
    return await metrics_service.list_agents_with_metrics(
        session,
        org_id=user.org_id,
        limit=limit,
        offset=offset,
        with_metrics=with_metrics,
        window=window,
        project=project,
    )


@router.post("", status_code=201)
async def create_agent(
    payload: AgentCreate,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    agent, token = await agents_service.create_agent(
        session, org_id=user.org_id, user_id=user.id, payload=payload
    )
    return {"agent": agents_service.agent_to_dict(agent), "token": token}


@router.post("/{name}/rotate-token")
async def rotate_token(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    token, prefix = await agents_service.rotate_token(session, org_id=user.org_id, name=name)
    return {"token": token, "token_prefix": prefix}


@router.post("/{name}/issue-token")
async def issue_token(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> dict:
    token, prefix = await agents_service.issue_token(session, org_id=user.org_id, name=name)
    return {"token": token, "token_prefix": prefix}


@router.delete("/{name}", status_code=204)
async def delete_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> None:
    await agents_service.delete_agent(session, org_id=user.org_id, name=name)


@router.get("/{name}", response_model=AgentDetail)
async def get_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentDetail:
    agent = await agents_service.get_agent_detail(session, org_id=user.org_id, name=name)
    return AgentDetail.model_validate(agent)


@router.patch("/{name}", response_model=AgentDetail)
async def patch_agent(
    name: str,
    patch: AgentPatch,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentDetail:
    agent = await agents_service.patch_agent(
        session, org_id=user.org_id, name=name, payload=patch
    )
    return AgentDetail.model_validate(agent)


@router.get("/{name}/metrics", response_model=AgentMetrics)
async def get_agent_metrics(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentMetrics:
    return await metrics_service.get_agent_metrics(
        session, org_id=user.org_id, name=name, window=window
    )


@router.get("/{name}/tools", response_model=list[AgentToolUsage])
async def get_agent_tools(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[AgentToolUsage]:
    return await metrics_service.get_agent_tools(
        session, org_id=user.org_id, name=name, window=window
    )


@router.get("/{name}/runs", response_model=AgentRunsResponse)
async def get_agent_runs(
    name: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    environment: Optional[str] = Query(default=None),
    version: Optional[str] = Query(default=None, description="version label"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> AgentRunsResponse:
    return await metrics_service.get_agent_runs(
        session,
        org_id=user.org_id,
        name=name,
        limit=limit,
        offset=offset,
        environment=environment,
        version=version,
    )


@router.get("/{name}/prompts", response_model=list[AgentPromptRow])
async def get_agent_prompts(
    name: str,
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[AgentPromptRow]:
    return await metrics_service.get_agent_prompts(
        session, org_id=user.org_id, name=name, limit=limit
    )


@router.get("/{name}/timeseries")
async def get_agent_timeseries(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    metrics: str = Query(default="p95_latency,cost_per_1k,tool_success,feedback_down"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[dict]:
    if window not in agent_timeseries.WINDOW_CONFIG:
        raise HTTPException(status_code=400, detail=f"invalid window {window!r}")
    metric_list = [m.strip() for m in metrics.split(",") if m.strip()]
    unknown = [m for m in metric_list if m not in agent_timeseries.SUPPORTED_METRICS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown metrics {unknown}")
    agent = await agents_service.resolve_agent(session, name, user.org_id)
    return await agent_timeseries.compute(
        session, agent_id=agent.id, window=window, metrics=metric_list
    )


@router.get("/{name}/worklist")
async def get_agent_worklist(
    name: str,
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> list[dict]:
    if window not in agent_worklist.WINDOW_HOURS:
        raise HTTPException(status_code=400, detail=f"invalid window {window!r}")
    agent = await agents_service.resolve_agent(session, name, user.org_id)
    return await agent_worklist.compute(session, agent_id=agent.id, window=window)


@router.get("/{name}/failures.csv")
async def get_agent_failures_csv(
    name: str,
    window: str = "7d",
    session: AsyncSession = Depends(get_session),
    user=require_user(),
):
    if window not in agent_worklist.WINDOW_HOURS:
        raise HTTPException(status_code=400, detail=f"invalid window {window!r}")
    agent = await agents_service.resolve_agent(session, name, user.org_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    base_url = os.environ.get("LANGPERF_WEB_BASE_URL", "http://localhost:3030")
    filename = f"agent-{agent.name}-failures.csv"
    return StreamingResponse(
        agent_failures.render_csv(
            session, agent_id=agent.id, window=window, web_base_url=base_url
        ),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{name}/profile.md")
async def get_agent_profile_md(
    name: str,
    window: str = "7d",
    session: AsyncSession = Depends(get_session),
    user=require_user(),
):
    if window not in agent_worklist.WINDOW_HOURS:
        raise HTTPException(status_code=400, detail=f"invalid window {window!r}")
    agent = await agents_service.resolve_agent(session, name, user.org_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    body = await agent_profile.render_markdown(
        session, agent_id=agent.id, window=window
    )
    filename = f"agent-{agent.name}-profile.md"
    return FastAPIResponse(
        content=body,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
