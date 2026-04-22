"""POST /v1/feedback — end-user thumbs-down/up capture.

Wire-format endpoint (lives under /v1/* to parallel /v1/traces) rather
than /api/* which is reserved for the web UI. Same bearer-token auth
pattern as OTLP ingest: the token's agent must own the target
trajectory or we 403.
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.agent_token import TOKEN_PREFIX_LEN, verify_token
from app.db import get_session
from app.models import Agent, Trajectory

logger = logging.getLogger("langperf.feedback")

router = APIRouter()


class FeedbackBody(BaseModel):
    trajectory_id: str = Field(min_length=1)
    thumbs: Literal["up", "down"]
    note: str | None = Field(default=None, max_length=4000)


@router.post("/v1/feedback", status_code=204)
async def receive_feedback(
    payload: FeedbackBody,
    authorization: str | None = Header(default=None, alias="authorization"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    token = _extract_bearer(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="bearer token required")

    agent = await _resolve_agent_by_token(session, token)
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid token")

    traj = (
        await session.execute(
            select(Trajectory).where(Trajectory.id == payload.trajectory_id)
        )
    ).scalar_one_or_none()
    if traj is None:
        raise HTTPException(status_code=404, detail="trajectory not found")
    if traj.agent_id != agent.id:
        raise HTTPException(
            status_code=403,
            detail="trajectory does not belong to the authenticated agent",
        )

    if payload.thumbs == "down":
        traj.feedback_thumbs_down = (traj.feedback_thumbs_down or 0) + 1
    else:
        traj.feedback_thumbs_up = (traj.feedback_thumbs_up or 0) + 1

    if payload.note:
        # Append rather than overwrite so earlier SME / SDK notes survive.
        # Separator is blank line so markdown renderers treat entries as paragraphs.
        existing = traj.notes or ""
        separator = "\n\n" if existing else ""
        marker = "[👎 feedback]" if payload.thumbs == "down" else "[👍 feedback]"
        traj.notes = f"{existing}{separator}{marker} {payload.note}"

    session.add(traj)
    await session.commit()
    return Response(status_code=204)


def _extract_bearer(header: str | None) -> str | None:
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


async def _resolve_agent_by_token(session: AsyncSession, token: str) -> Agent | None:
    prefix = token[:TOKEN_PREFIX_LEN]
    row = (
        await session.execute(select(Agent).where(Agent.token_prefix == prefix))
    ).scalar_one_or_none()
    if row is None or row.token_hash is None:
        return None
    if not verify_token(token, row.token_hash):
        return None
    return row
