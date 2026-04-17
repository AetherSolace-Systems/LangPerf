import asyncio
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.agents import router as agents_router
from app.api.nodes import router as nodes_router
from app.api.overview import router as overview_router
from app.api.runs import router as runs_router
from app.api.trajectories import router as trajectories_router
from app.db import engine
from app.otlp.receiver import router as otlp_router

logging.basicConfig(
    level=os.environ.get("LANGPERF_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
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
    logger.info("langperf-api ready")
    yield
    await engine.dispose()


app = FastAPI(title="LangPerf API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"service": "langperf-api", "version": "0.1.0"}


@app.get("/healthz")
async def healthz():
    return {"ok": True}


app.include_router(otlp_router)
app.include_router(trajectories_router)
app.include_router(nodes_router)
app.include_router(agents_router)
app.include_router(overview_router)
app.include_router(runs_router)
