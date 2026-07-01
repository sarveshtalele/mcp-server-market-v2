"""Data API entrypoint.

A single FastAPI application that auto-mounts every module's router via the
registry. Adding a module with a `router` makes its endpoints appear here with
no change to this file.

Run:
    uvicorn data_api.main:app --reload --port 8000
Docs at http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import init_db
from core.logging_config import get_logger
from core.registry import discover_modules

log = get_logger("data_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    names = [s.name for s in discover_modules()]
    log.info("Data API ready - modules mounted: %s", ", ".join(names))
    yield


app = FastAPI(
    title="Stock Exchange Data API",
    description="Synthetic stock-exchange data, served by pluggable modules.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with its status and latency (debug-friendly)."""
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    log.info(
        "%s %s -> %d (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response

# Auto-mount every module that exposes a router.
_MODULES = discover_modules()
for spec in _MODULES:
    if spec.router is not None:
        app.include_router(spec.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "currency": settings.currency,
        "modules": [
            {
                "name": s.name,
                "description": s.description,
                "has_api": s.router is not None,
                "has_tools": s.register_tools is not None,
            }
            for s in _MODULES
        ],
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "Stock Exchange Data API",
        "docs": "/docs",
        "modules": [s.name for s in _MODULES],
    }
