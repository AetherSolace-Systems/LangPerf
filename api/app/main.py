import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.otlp.receiver import router as otlp_router

logging.basicConfig(
    level=os.environ.get("LANGPERF_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="LangPerf API", version="0.1.0")

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
