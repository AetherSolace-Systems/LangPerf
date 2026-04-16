import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.trajectories import router as trajectories_router
from app.db import engine
from app.models import Base
from app.otlp.receiver import router as otlp_router

logging.basicConfig(
    level=os.environ.get("LANGPERF_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("langperf")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # v1 uses metadata.create_all() instead of Alembic — fine at dogfood scale.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
