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
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse

from core.config import BACKEND_ROOT, settings
from core.database import init_db
from core.logging_config import get_logger
from core.registry import discover_modules

log = get_logger("data_api")

# agentgateway has no built-in log viewer/API - it only ever writes to
# whatever file/console you redirect its stdout/stderr to when launching it
# (see backend/mcp_server/gateway/run.ps1). This just tails those files in a
# browser instead of needing a terminal window.
_GATEWAY_LOG_DIR = BACKEND_ROOT / "mcp_server" / "gateway"


def _tail(path: Path, n: int) -> str:
    if not path.exists():
        return f"(no log file yet - is the gateway running with output redirected to {path.name}?)"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:]) or "(empty)"


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


@app.get("/gateway-logs/raw", tags=["meta"])
def gateway_logs_raw(lines: int = 300) -> PlainTextResponse:
    """Plain-text tail of the agentgateway process's stdout/stderr log files."""
    body = (
        f"=== stdout (audit log: one line per MCP call) ===\n"
        f"{_tail(_GATEWAY_LOG_DIR / 'stdout.log', lines)}\n\n"
        f"=== stderr (the wrapped mcp_server.server process's own output) ===\n"
        f"{_tail(_GATEWAY_LOG_DIR / 'stderr.log', lines)}"
    )
    return PlainTextResponse(body)


@app.get("/gateway-logs", tags=["meta"])
def gateway_logs_page() -> HTMLResponse:
    """Auto-refreshing browser view of the agentgateway logs - it has no log viewer of its own."""
    html = """<!doctype html>
<html><head><title>agentgateway logs</title>
<style>
  body { font-family: ui-monospace, "SF Mono", Menlo, monospace; background: #111; color: #ddd; margin: 0; padding: 14px; }
  h3 { color: #8ecfff; margin: 0 0 10px; font-size: 14px; }
  pre { white-space: pre-wrap; word-break: break-all; font-size: 12.5px; line-height: 1.5; }
</style></head>
<body>
  <h3>agentgateway + MCP server logs &middot; auto-refreshes every 2s</h3>
  <pre id="log">loading...</pre>
  <script>
    async function refresh() {
      const atBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 40;
      const r = await fetch('/gateway-logs/raw?lines=400');
      document.getElementById('log').textContent = await r.text();
      if (atBottom) window.scrollTo(0, document.body.scrollHeight);
    }
    refresh();
    setInterval(refresh, 2000);
  </script>
</body></html>"""
    return HTMLResponse(html)


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
