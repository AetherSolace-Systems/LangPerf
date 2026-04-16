"""OTLP/HTTP receiver — POST /v1/traces.

M1: decode + log spans. No persistence yet.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Header, Request, Response

from app.otlp.decoder import decode

logger = logging.getLogger("langperf.otlp")

router = APIRouter()


@router.post("/v1/traces")
async def receive_traces(
    request: Request,
    content_type: str | None = Header(default="application/x-protobuf"),
):
    body = await request.body()
    try:
        bundles = decode(body, content_type or "application/x-protobuf")
    except Exception as exc:
        logger.exception("failed to decode OTLP body: %s", exc)
        # OTLP spec says partial_success is the right response shape for recoverable errors.
        # For unrecoverable decode errors we return 400.
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
    for bundle in bundles:
        for span in bundle["spans"]:
            logger.info(
                "  span name=%r kind=%s trace_id=%s span_id=%s parent=%s "
                "attrs.keys=%s",
                span["name"],
                span["kind"],
                span["trace_id"],
                span["span_id"],
                span["parent_span_id"],
                list(span["attributes"].keys()),
            )

    # OTLP/HTTP success response — empty ExportTraceServiceResponse is valid
    return Response(content=b"", media_type="application/x-protobuf", status_code=200)
