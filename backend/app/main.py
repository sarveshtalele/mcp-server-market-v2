"""Backend entrypoint — one process, four surfaces.

    /mcp             MCP 2026-07-28 over Streamable HTTP (what the gateway targets)
    /agui            AG-UI event stream for the web chat
    /listings /filings   REST
    /observability   audit query API for the Control Room

Run:
    uvicorn app.main:app --port 8000

Everything is mounted from the module registry, so adding a package under
``modules/`` wires it into all of the above with no edit to this file.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from ag_ui.core import RunAgentInput
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from agui_agent.agent import ExchangeAgent
from app.middleware import ProtocolGuardMiddleware, RequestLogMiddleware
from core.config import PROTOCOL_VERSION, settings
from core.database import init_db
from core.logging_config import get_logger
from core.registry import discover_modules
from mcp_client.session import MCPClientError
from mcp_server.server import mcp, transport_security
from modules.observability import repository as obs_repo
from modules.observability.hub import hub
from modules.observability.ingester import GatewayLogIngester
from modules.observability.recorder import CallRecorderMiddleware
from modules.observability.store import ObsSessionLocal, init_obs_db

log = get_logger("app")

agent = ExchangeAgent()
_ingester = GatewayLogIngester()

# The MCP ASGI app. Origin/Host validation is mandatory for this transport.
mcp_asgi = mcp.streamable_http_app(
    streamable_http_path=settings.mcp_path,
    transport_security=transport_security(),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_obs_db()
    hub.bind_loop(asyncio.get_running_loop())

    with ObsSessionLocal() as db:
        removed = obs_repo.prune(db)
    if removed:
        log.info("audit retention: pruned %d row(s)", removed)

    await agent.startup()
    _ingester.start()

    names = [s.name for s in discover_modules()]
    log.info(
        "Backend ready on http://%s:%d — MCP %s at %s — modules: %s",
        settings.host,
        settings.port,
        PROTOCOL_VERSION,
        settings.mcp_path,
        ", ".join(names),
    )

    # The MCP session manager runs for the lifetime of the app.
    async with mcp_asgi.router.lifespan_context(app):
        yield

    await _ingester.stop()
    await agent.shutdown()


app = FastAPI(
    title="Stock Exchange MCP Backend",
    description=("Synthetic stock-exchange data served over MCP 2026-07-28, REST and AG-UI."),
    version=settings.client_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Explicit origins only. "*" would defeat the Origin validation the MCP
    # transport requires.
    allow_origins=settings.cors_origins,
    # PUT is needed for the allowlist editor on the MCP Servers page.
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["content-type", "accept", "authorization", "mcp-protocol-version"],
)


app.add_middleware(RequestLogMiddleware)


# --- REST + observability routers, from the registry -----------------------
_MODULES = discover_modules()
for spec in _MODULES:
    if spec.router is not None:
        app.include_router(spec.router)


# --- AG-UI -----------------------------------------------------------------
@app.post("/agui", tags=["agui"])
async def agui_endpoint(input_data: RunAgentInput, request: Request) -> StreamingResponse:
    """AG-UI run endpoint consumed by the browser chat."""
    accept = request.headers.get("accept")
    log.info(
        "run %s (thread %s) - %d message(s)",
        input_data.run_id,
        input_data.thread_id,
        len(input_data.messages),
    )
    return StreamingResponse(
        agent.run(input_data, accept),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@app.get("/agui/capabilities", tags=["agui"])
async def capabilities() -> JSONResponse:
    """What the MCP server offers, and what actually survives the gateway.

    These are two different things, and the UI must not conflate them.
    agentgateway 1.4.1 proxies tools faithfully but returns empty resource,
    template and prompt lists, and rewrites the cache hints. Reporting only the
    gateway's view would make a working capability look missing; reporting only
    the server's view would claim reachability the consumers do not have.
    """
    declared = {
        "server_name": mcp.name,
        "server_version": mcp.version,
        "protocol_version": PROTOCOL_VERSION,
        "instructions": mcp.instructions,
        "tools": sorted(t.name for t in mcp._tool_manager.list_tools()),  # noqa: SLF001
        "resources": sorted(str(r.uri) for r in await mcp.list_resources()),
        "resource_templates": sorted(t.uri_template for t in await mcp.list_resource_templates()),
        "prompts": sorted(p.name for p in await mcp.list_prompts()),
        "cache_ttl_ms": settings.mcp_cache_ttl_ms,
    }
    payload: dict = {"declared": declared, "gateway_url": agent.mcp.url}
    try:
        payload["reachable"] = await agent.mcp.capabilities()
        payload["gateway_connected"] = True
    except MCPClientError as exc:
        payload["reachable"] = None
        payload["gateway_connected"] = False
        payload["gateway_error"] = str(exc)
    return JSONResponse(payload)


# --- meta ------------------------------------------------------------------
@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "protocol_version": PROTOCOL_VERSION,
        "currency": settings.currency,
        "data": "synthetic",
        "mcp_endpoint": settings.mcp_path,
        "gateway_url": settings.mcp_gateway_url,
        "mcp_connected": agent.mcp.connected,
        "modules": [
            {
                "name": s.name,
                "description": s.description,
                "has_api": s.router is not None,
                "has_tools": s.register_tools is not None,
                "has_resources": s.register_resources is not None,
                "has_prompts": s.register_prompts is not None,
            }
            for s in _MODULES
        ],
    }


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "service": "Stock Exchange MCP Backend",
        "protocol_version": PROTOCOL_VERSION,
        "docs": "/docs",
        "mcp": settings.mcp_path,
        "modules": [s.name for s in _MODULES],
    }


# --- MCP transport ---------------------------------------------------------
# Sessions, the GET stream and DELETE were all removed from the transport in
# 2026-07-28. Answer them explicitly rather than letting them 404, so an older
# client gets the documented signal.
_GONE = {
    "jsonrpc": "2.0",
    "error": {
        "code": -32600,
        "message": (
            "Method Not Allowed. MCP 2026-07-28 uses POST only: the GET stream, "
            "DELETE termination and Mcp-Session-Id were removed from the transport."
        ),
    },
}


@app.get(settings.mcp_path, include_in_schema=False)
@app.delete(settings.mcp_path, include_in_schema=False)
async def mcp_method_not_allowed() -> JSONResponse:
    return JSONResponse(_GONE, status_code=405)


# Mounted last so the explicit routes above win. Every POST that reaches the MCP
# app passes through the recorder, which is what fills the audit log.
app.mount(
    "/",
    ProtocolGuardMiddleware(
        CallRecorderMiddleware(mcp_asgi),
        version=PROTOCOL_VERSION,
        strict=settings.strict_protocol,
    ),
)
