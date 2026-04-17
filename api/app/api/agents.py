"""Agents list / detail / PATCH endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Agent
from app.schemas import AgentDetail, AgentPatch, AgentSummary

router = APIRouter(prefix="/api/agents")

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


@router.get("", response_model=list[AgentSummary])
async def list_agents(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AgentSummary]:
    result = await session.execute(
        select(Agent).order_by(Agent.name).limit(limit).offset(offset)
    )
    return [AgentSummary.model_validate(a) for a in result.scalars().all()]


@router.get("/{name}", response_model=AgentDetail)
async def get_agent(
    name: str,
    session: AsyncSession = Depends(get_session),
) -> AgentDetail:
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name)
        .options(selectinload(Agent.versions))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return AgentDetail.model_validate(agent)


@router.patch("/{name}", response_model=AgentDetail)
async def patch_agent(
    name: str,
    patch: AgentPatch,
    session: AsyncSession = Depends(get_session),
) -> AgentDetail:
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name)
        .options(selectinload(Agent.versions))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")

    if patch.rename_to is not None:
        new_name = patch.rename_to.strip().lower()
        if not NAME_RE.match(new_name):
            raise HTTPException(
                status_code=400,
                detail="name must be lowercase letters/digits/hyphens, 1–64 chars, starting alphanumeric",
            )
        collision = (
            await session.execute(
                select(Agent.id).where(Agent.name == new_name, Agent.id != agent.id)
            )
        ).scalar_one_or_none()
        if collision:
            raise HTTPException(status_code=409, detail="name already in use")
        agent.name = new_name

    if patch.display_name is not None:
        agent.display_name = patch.display_name or None
    if patch.description is not None:
        agent.description = patch.description or None
    if patch.owner is not None:
        agent.owner = patch.owner or None
    if patch.github_url is not None:
        agent.github_url = patch.github_url or None

    await session.commit()
    await session.refresh(agent)
    return AgentDetail.model_validate(agent)
