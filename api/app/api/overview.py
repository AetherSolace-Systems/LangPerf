"""Dashboard aggregation endpoint — scopes counts, tools, and heatmap
across every agent ingested into this workspace.

Thin HTTP-adapter layer — all aggregation logic lives in
`app.services.overview`. Designed to fit on a single HTTP response so the
Dashboard is one fetch. All aggregates bucketed by the `window` query param
(24h / 7d / 30d).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.schemas import OverviewResponse
from app.services import overview as overview_service

router = APIRouter(prefix="/api/overview")


@router.get("", response_model=OverviewResponse)
async def get_overview(
    window: str = Query(default="7d", pattern="^(24h|7d|30d)$"),
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> OverviewResponse:
    return await overview_service.build_overview(
        session, org_id=user.org_id, window=window
    )
