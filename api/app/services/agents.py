"""Agent CRUD / token service layer.

Extracted from `app.api.agents` to keep the HTTP-adapter layer thin. Every
function here takes an `AsyncSession` plus keyword args and returns domain
objects (SQLAlchemy models, tuples, raw strings). The functions raise
`HTTPException` directly — mirroring the behaviour of the inline code they
replaced — so the route handlers can stay one-liners.
"""

from __future__ import annotations

import re
import uuid as _uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.agent_token import generate_token, hash_token
from app.models import Agent
from app.projects.helpers import get_default_project_id, get_project_by_slug
from app.schemas import AgentPatch, AgentSummary

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    display_name: str | None = None
    description: str | None = None
    language: str | None = None
    github_url: str | None = None
    project_slug: str | None = None


def agent_to_dict(agent: Agent) -> dict:
    """Serialize an Agent ORM row to the public summary shape."""
    return AgentSummary.model_validate(agent).model_dump(mode="json")


async def resolve_agent(session: AsyncSession, name: str, org_id: str) -> Agent:
    result = await session.execute(
        select(Agent).where(Agent.name == name, Agent.org_id == org_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


async def create_agent(
    session: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    payload: AgentCreate,
) -> tuple[Agent, str]:
    """Create a new agent and mint its first token. Returns (agent, raw_token)."""
    existing = (
        await session.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.name == payload.name)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"agent {payload.name!r} already exists")
    if payload.project_slug:
        proj = await get_project_by_slug(session, org_id, payload.project_slug)
        if proj is None:
            raise HTTPException(
                status_code=404, detail=f"project {payload.project_slug!r} not found"
            )
        project_id = proj.id
    else:
        project_id = await get_default_project_id(session, org_id)
    token, prefix = generate_token()
    agent = Agent(
        org_id=org_id,
        signature=f"registered:{_uuid.uuid4()}",
        name=payload.name,
        display_name=payload.display_name,
        description=payload.description,
        language=payload.language,
        github_url=payload.github_url,
        token_hash=hash_token(token),
        token_prefix=prefix,
        created_by_user_id=user_id,
        project_id=project_id,
    )
    session.add(agent)
    await session.commit()
    agent = (
        await session.execute(
            select(Agent)
            .where(Agent.id == agent.id)
            .options(selectinload(Agent.project))
        )
    ).scalar_one()
    return agent, token


async def rotate_token(session: AsyncSession, *, org_id: str, name: str) -> tuple[str, str]:
    """Mint a fresh token for an existing agent. Returns (raw_token, prefix)."""
    agent = (
        await session.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.name == name)
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    token, prefix = generate_token()
    agent.token_hash = hash_token(token)
    agent.token_prefix = prefix
    agent.last_token_used_at = None
    await session.commit()
    return token, prefix


async def issue_token(session: AsyncSession, *, org_id: str, name: str) -> tuple[str, str]:
    """Mint a token on a legacy agent that has never had one."""
    agent = (
        await session.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.name == name)
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    if agent.token_hash is not None:
        raise HTTPException(status_code=409, detail="agent already has a token; rotate instead")
    token, prefix = generate_token()
    agent.token_hash = hash_token(token)
    agent.token_prefix = prefix
    await session.commit()
    return token, prefix


async def delete_agent(session: AsyncSession, *, org_id: str, name: str) -> None:
    agent = (
        await session.execute(
            select(Agent).where(Agent.org_id == org_id, Agent.name == name)
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    await session.delete(agent)
    await session.commit()


async def get_agent_detail(session: AsyncSession, *, org_id: str, name: str) -> Agent:
    """Load a full agent row with versions/project eager-loaded."""
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name, Agent.org_id == org_id)
        .options(selectinload(Agent.versions), selectinload(Agent.project))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


async def patch_agent(
    session: AsyncSession,
    *,
    org_id: str,
    name: str,
    payload: AgentPatch,
) -> Agent:
    result = await session.execute(
        select(Agent)
        .where(Agent.name == name, Agent.org_id == org_id)
        .options(selectinload(Agent.versions), selectinload(Agent.project))
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")

    if payload.rename_to is not None:
        new_name = payload.rename_to.strip().lower()
        if not NAME_RE.match(new_name):
            raise HTTPException(
                status_code=400,
                detail="name must be lowercase letters/digits/hyphens, 1–64 chars, starting alphanumeric",
            )
        collision = (
            await session.execute(
                select(Agent.id).where(
                    Agent.name == new_name,
                    Agent.id != agent.id,
                    Agent.org_id == org_id,
                )
            )
        ).scalar_one_or_none()
        if collision:
            raise HTTPException(status_code=409, detail="name already in use")
        agent.name = new_name

    if payload.display_name is not None:
        agent.display_name = payload.display_name or None
    if payload.description is not None:
        agent.description = payload.description or None
    if payload.owner is not None:
        agent.owner = payload.owner or None
    if payload.github_url is not None:
        agent.github_url = payload.github_url or None
    if payload.project_slug is not None:
        proj = await get_project_by_slug(session, org_id, payload.project_slug)
        if proj is None:
            raise HTTPException(status_code=404, detail="project not found")
        agent.project_id = proj.id

    await session.commit()
    agent_id = agent.id
    session.expire(agent)
    agent = (
        await session.execute(
            select(Agent)
            .where(Agent.id == agent_id)
            .options(selectinload(Agent.versions), selectinload(Agent.project))
        )
    ).scalar_one()
    return agent
