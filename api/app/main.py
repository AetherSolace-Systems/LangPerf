import asyncio
import contextlib
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth as auth_api
from app.api import projects as projects_api
from app.api.agents import router as agents_router
from app.api.comments import router as comments_router
from app.api.notifications import router as notifications_router
from app.api.reviewers import router as reviewers_router
from app.api.shared_links import router as shared_links_router
from app.api.failure_modes import router as failure_modes_router
from app.api import triage as triage_api
from app.api import clusters as clusters_api
from app.api import rewrites as rewrites_api
from app.api.logs import router as logs_router
from app.api.nodes import router as nodes_router
from app.api.overview import router as overview_router
from app.api.runs import router as runs_router
from app.api.settings import router as settings_router
from app.api.trajectories import router as trajectories_router
from app.db import engine
from app.logs import attach_handler
from app.logs.file_forwarder import start_background_task as start_file_forwarder
from app.otlp.receiver import router as otlp_router

logging.basicConfig(
    level=os.environ.get("LANGPERF_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
attach_handler(level=logging._nameToLevel.get(os.environ.get("LANGPERF_LOG_LEVEL", "INFO"), logging.INFO))
logger = logging.getLogger("langperf")


async def _is_pre_alembic_db() -> bool:
    """Return True iff trajectories exists but alembic_version does not."""
    async with engine.begin() as conn:
        trajectories = (
            await conn.execute(
                text(
                    "SELECT to_regclass('public.trajectories') IS NOT NULL AS present"
                )
            )
        ).scalar_one()
        alembic_version = (
            await conn.execute(
                text(
                    "SELECT to_regclass('public.alembic_version') IS NOT NULL AS present"
                )
            )
        ).scalar_one()
    return bool(trajectories) and not bool(alembic_version)


def _run_alembic(*args: str) -> None:
    """Run an alembic CLI command in a subprocess to avoid asyncio loop conflicts.

    env.py calls asyncio.run() at module level, which cannot be nested inside
    the already-running FastAPI event loop — even via asyncio.to_thread the
    inner loop's cleanup can deadlock.  A subprocess has its own interpreter
    and event loop, so there is no conflict.
    """
    cmd = [sys.executable, "-m", "alembic", *args]
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"alembic {' '.join(args)} failed (exit {result.returncode})")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if await _is_pre_alembic_db():
        logger.info("pre-Alembic DB detected — stamping baseline (0001)")
        await asyncio.to_thread(_run_alembic, "stamp", "0001")
    logger.info("alembic upgrade head")
    await asyncio.to_thread(_run_alembic, "upgrade", "head")
    file_fwd_task = start_file_forwarder()
    logger.info("langperf-api ready")
    try:
        yield
    finally:
        file_fwd_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await file_fwd_task
        await engine.dispose()


app = FastAPI(title="LangPerf API", version="0.1.0", lifespan=lifespan)

_default_origins = "http://localhost:3030,http://127.0.0.1:3030"
_cors_origins = [
    o.strip() for o in os.environ.get("LANGPERF_CORS_ORIGINS", _default_origins).split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "langperf-api", "version": "0.1.0"}


@app.get("/healthz")
async def healthz():
    return {"ok": True}


app.include_router(auth_api.router)
app.include_router(projects_api.router)
app.include_router(otlp_router)
app.include_router(trajectories_router)
app.include_router(nodes_router)
app.include_router(agents_router)
app.include_router(overview_router)
app.include_router(runs_router)
app.include_router(logs_router)
app.include_router(settings_router)
app.include_router(comments_router)
app.include_router(notifications_router)
app.include_router(reviewers_router)
app.include_router(shared_links_router)
app.include_router(failure_modes_router)
app.include_router(triage_api.router)
app.include_router(clusters_api.router)
app.include_router(rewrites_api.router)
