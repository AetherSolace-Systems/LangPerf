"""OTLP/HTTP receiver — `POST /v1/traces`.

Thin HTTP boundary: decode the OTLP body, hand the decoded bundles to
`app.otlp.ingest`, commit once, and respond with an empty success. All
DB logic lives in ingest.py so it is testable without FastAPI.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.ingest.org import get_default_org_id
from app.otlp.decoder import decode
from app.otlp.ingest import ingest_bundles, recompute_totals

logger = logging.getLogger("langperf.otlp")

router = APIRouter()


@router.post("/v1/traces")
async def receive_traces(
    request: Request,
    content_type: str | None = Header(default="application/x-protobuf"),
    session: AsyncSession = Depends(get_session),
):
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
        "received %d span(s) in %d resource-bundle(s) (content-type=%s, bytes=%d)",
        span_count,
        len(bundles),
        content_type,
        len(body),
    )

    # TODO(v2b): scope OTLP ingestion per API key once we add api_keys table
    org_id = await get_default_org_id(session)

    touched = await ingest_bundles(session, bundles, org_id)
    await recompute_totals(session, touched)
    await session.commit()

    return Response(content=b"", media_type="application/x-protobuf", status_code=200)
