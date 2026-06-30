"""Data API entrypoint.

A single FastAPI application that auto-mounts every module's router via the
registry. Adding a module with a `router` makes its endpoints appear here with
no change to this file.

Run:
    uvicorn data_api.main:app --reload --port 8000
Docs at http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.database import init_db
from core.registry import discover_modules


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
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
