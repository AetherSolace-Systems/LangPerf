"""/api/settings — UI-managed workspace configuration.

Backed by the `workspace_settings` key/value table. Each endpoint knows a
specific setting key and validates its value shape.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import require_user
from app.db import get_session
from app.models import WorkspaceSetting

router = APIRouter(prefix="/api/settings")
logger = logging.getLogger("langperf.settings")


# ── Shapes ────────────────────────────────────────────────────────────────


class FileTarget(BaseModel):
    enabled: bool = False
    path: str = "/var/log/langperf/events.jsonl"
    rotate_daily: bool = True
    keep_days: int = 14


class DatadogTarget(BaseModel):
    enabled: bool = False
    site: str = "datadoghq.com"
    # API key lives in the DD_API_KEY env var; we store only the flag of whether it's configured.
    api_key_env: str = "DD_API_KEY"


class LokiTarget(BaseModel):
    enabled: bool = False
    endpoint: str = ""
    labels: dict[str, str] = Field(default_factory=dict)


class OtlpTarget(BaseModel):
    enabled: bool = False
    endpoint: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


class ForwardingKinds(BaseModel):
    server_logs: bool = True
    trace_events: bool = True
    full_payloads: bool = False
    sdk_diagnostics: bool = False


class LogForwardingConfig(BaseModel):
    file: FileTarget = Field(default_factory=FileTarget)
    datadog: DatadogTarget = Field(default_factory=DatadogTarget)
    loki: LokiTarget = Field(default_factory=LokiTarget)
    otlp: OtlpTarget = Field(default_factory=OtlpTarget)
    kinds: ForwardingKinds = Field(default_factory=ForwardingKinds)


KEY_LOG_FORWARDING = "log_forwarding"


# ── Storage ───────────────────────────────────────────────────────────────


async def _load(session: AsyncSession, org_id: str, key: str) -> Optional[dict[str, Any]]:
    row = (
        await session.execute(
            select(WorkspaceSetting.value).where(
                WorkspaceSetting.org_id == org_id,
                WorkspaceSetting.key == key,
            )
        )
    ).scalar_one_or_none()
    return row


async def _save(session: AsyncSession, org_id: str, key: str, value: dict[str, Any]) -> None:
    stmt = pg_insert(WorkspaceSetting).values(org_id=org_id, key=key, value=value)
    stmt = stmt.on_conflict_do_update(
        index_elements=[WorkspaceSetting.org_id, WorkspaceSetting.key],
        set_={"value": stmt.excluded.value},
    )
    await session.execute(stmt)
    await session.commit()


# ── Routes ────────────────────────────────────────────────────────────────


@router.get("/log-forwarding", response_model=LogForwardingConfig)
async def get_log_forwarding(
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> LogForwardingConfig:
    raw = await _load(session, user.org_id, KEY_LOG_FORWARDING)
    if raw is None:
        return LogForwardingConfig()
    return LogForwardingConfig.model_validate(raw)


@router.put("/log-forwarding", response_model=LogForwardingConfig)
async def put_log_forwarding(
    cfg: LogForwardingConfig,
    session: AsyncSession = Depends(get_session),
    user=require_user(),
) -> LogForwardingConfig:
    await _save(session, user.org_id, KEY_LOG_FORWARDING, cfg.model_dump())
    logger.info(
        "log-forwarding config updated: file=%s datadog=%s loki=%s otlp=%s",
        cfg.file.enabled,
        cfg.datadog.enabled,
        cfg.loki.enabled,
        cfg.otlp.enabled,
    )
    return cfg
