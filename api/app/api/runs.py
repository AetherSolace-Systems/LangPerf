"""`GET /api/runs` — global run search with fuzzy agent.env.version pattern.

The pattern is split on `.` into at most three segments: agent, environment,
version. Each segment is a shell-style glob (`*` matches any char sequence,
literal otherwise). Missing trailing segments default to `*`.

Examples
--------
    support-*.prod.*       → support-* agents in prod, any version
    triage-router.*.v2.*   → triage-router in any env, version labels starting v2.
    *.test.*               → all agents in env "test"
    v1.4.*                 → matches against the agent slot; usually not what
                              you want. Use "*.*.v1.4.*" to filter by version.

Thin HTTP-adapter layer — all query logic lives in `app.services.runs`.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.schemas import RunsResponse
from app.services import runs as runs_service

router = APIRouter(prefix="/api/runs")


@router.get("", response_model=RunsResponse)
async def list_runs(
    pattern: Optional[str] = Query(default=None, description="agent.env.version glob"),
    tag: Optional[str] = Query(default=None, description="good|bad|interesting|todo|none"),
    q: Optional[str] = Query(default=None, description="free-text search"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> RunsResponse:
    return await runs_service.list_runs(
        session,
        org_id=user.org_id,
        pattern=pattern,
        tag=tag,
        q=q,
        limit=limit,
        offset=offset,
    )
