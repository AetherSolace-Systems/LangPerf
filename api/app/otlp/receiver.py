"""OTLP/HTTP receiver — `POST /v1/traces`.

Thin HTTP boundary: decode the OTLP body, hand the decoded bundles to
`app.otlp.ingest`, commit once, and respond with an empty success. All
DB logic lives in ingest.py so it is testable without FastAPI.

Auth: every request must present a valid `Authorization: Bearer <token>`
header. The token's agent is authoritative — ingested spans are bound to
that agent's id regardless of any `service.name`/signature in the OTLP
resource attributes.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.agent_token import TOKEN_PREFIX_LEN, verify_token
from app.db import SessionLocal, get_session
from app.ingest.hook import schedule_heuristics
from app.models import Agent
from app.otlp.decoder import decode
from app.otlp.ingest import ingest_bundles, recompute_totals

logger = logging.getLogger("langperf.otlp")

router = APIRouter()


@router.post("/v1/traces")
async def receive_traces(
    request: Request,
    content_type: str | None = Header(default="application/x-protobuf"),
    authorization: str | None = Header(default=None, alias="authorization"),
    session: AsyncSession = Depends(get_session),
):
    token = _extract_bearer(authorization)
    if token is None:
        raise HTTPException(status_code=401, detail="bearer token required")
    agent = await _resolve_agent_by_token(session, token)
    if agent is None:
        raise HTTPException(status_code=401, detail="invalid token")

    body = await request.body()
    try:
        bundles = decode(body, content_type or "application/x-protobuf")
    except Exception as exc:
        logger.exception("failed to decode OTLP body: %s", exc)
        return Response(
            content=json.dumps({"error": str(exc)}),
            status_code=400,
            media_type="application/json",
        )

    span_count = sum(len(b["spans"]) for b in bundles)
    logger.info(
        "received %d span(s) in %d resource-bundle(s) (content-type=%s, bytes=%d, agent=%s)",
        span_count,
        len(bundles),
        content_type,
        len(body),
        agent.name,
    )

    touched = await ingest_bundles(session, bundles, org_id=agent.org_id, agent=agent)
    await recompute_totals(session, touched)
    agent.last_token_used_at = datetime.now(timezone.utc)
    session.add(agent)
    await session.commit()

    schedule_heuristics(SessionLocal, list(touched))

    return Response(content=b"", media_type="application/x-protobuf", status_code=200)


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
