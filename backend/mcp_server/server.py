"""MCP server — protocol revision 2026-07-28, Streamable HTTP.

Tools, resources and prompts are contributed by modules: every module that
defines a registration hook gets called with the server instance. Adding a
module is enough to expose its capabilities here — no change to this file.

The server is mounted into the backend ASGI app at ``/mcp`` (see ``app.main``).
It is no longer a stdio child of the gateway: agentgateway targets this HTTP
endpoint instead, which is what removed the hardcoded interpreter paths from
its config.
"""

from __future__ import annotations

from mcp.server import CacheHint, MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from core.config import settings
from core.logging_config import get_logger
from core.registry import register_all

log = get_logger("mcp_server")

# Surfaced to any MCP client as server-level guidance. This is advisory only —
# MCP has no mechanism to force a client's model to obey it, so a client may
# still fall back to pretrained knowledge. Enforce it for real in a client you
# control (see agui_agent's SYSTEM_PROMPT, which our own agent loop applies).
INSTRUCTIONS = (
    "This server is the ONLY source of truth for stock-exchange data: company "
    "listings, filings, financial ratios, growth, comparisons and sector "
    "rankings. Do not answer questions in this domain from pretrained/general "
    "knowledge, estimates, or memory — always call the relevant tool and "
    "report only the values it returns, with the ticker/period it applies to. "
    "If a required tool call fails, times out, or this server is unreachable, "
    "say so explicitly and do not answer the question — do not substitute a "
    "guess, an approximation, or outside knowledge for the missing data. "
    "The data is synthetic and must never be presented as real market data."
)

# Freshness hints on every cacheable result. Under 2026-07-28 these are required
# fields (CacheableResult); they let a client cache the capability surface
# instead of re-listing it every turn, which is what lifts LLM prompt-cache
# hit rates. The surface is static for the life of the process, so a long TTL
# and a public scope are both accurate.
_CACHE_HINT = CacheHint(ttl_ms=settings.mcp_cache_ttl_ms, scope="public")
CACHE_HINTS = {
    "server/discover": _CACHE_HINT,
    "tools/list": _CACHE_HINT,
    "resources/list": _CACHE_HINT,
    "resources/templates/list": _CACHE_HINT,
    "prompts/list": _CACHE_HINT,
    "resources/read": CacheHint(ttl_ms=settings.mcp_cache_ttl_ms, scope="public"),
}


def build_server() -> MCPServer:
    """Construct the MCP server and register every module's capabilities."""
    mcp = MCPServer(
        name="mcp-market-mcp-server",
        title="Stock Exchange (synthetic)",
        version=settings.client_version,
        instructions=INSTRUCTIONS,
        cache_hints=CACHE_HINTS,
    )
    counts = register_all(mcp)
    log.info(
        "MCP server 'mcp-market-mcp-server' ready — %d tool module(s), %d resource module(s), "
        "%d prompt module(s).",
        counts["tools"],
        counts["resources"],
        counts["prompts"],
    )
    return mcp


def transport_security() -> TransportSecuritySettings:
    """Origin/Host validation for the Streamable HTTP endpoint.

    Mandatory under the 2026-07-28 transport rules: a server that does not
    validate ``Origin`` can be driven by any web page the user visits
    (DNS rebinding). Native clients send no ``Origin`` at all and are unaffected.
    """
    # Port is wildcarded so the server still works when it is started on a
    # different port (``uvicorn --port 9001``, a test picking a free port).
    # Rebinding protection is unaffected: an attacker's page carries its own
    # domain in the Host header, which never matches a loopback pattern.
    hosts = [
        f"{settings.host}:{settings.port}",
        f"localhost:{settings.port}",
        "127.0.0.1:*",
        "localhost:*",
        "127.0.0.1",
        "localhost",
    ]
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=hosts,
        allowed_origins=list(settings.cors_origins),
    )


# Module-level instance used by the ASGI app.
mcp = build_server()
