"""MCP server (FastMCP, stdio transport).

Tools are contributed by modules: every module that defines `register_tools`
gets called with the FastMCP instance and a shared Data API client. Adding a
module is enough to expose its tools here — no change to this file.

Run standalone for Claude Desktop / Claude Code:
    python -m mcp_server.server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core.logging_config import get_logger
from core.registry import discover_modules
from mcp_server.api_client import DataAPIClient

log = get_logger("mcp_server")
mcp = FastMCP("stock-exchange")
api = DataAPIClient()

# Register tools from every module that provides them. Logging goes to stderr so
# it never corrupts the stdio JSON-RPC channel on stdout.
_registered = 0
for spec in discover_modules():
    if spec.register_tools is not None:
        spec.register_tools(mcp, api)
        _registered += 1
log.info("MCP server 'stock-exchange' ready - tools from %d module(s).", _registered)


if __name__ == "__main__":
    # Default transport is stdio — the form Claude Desktop / Code expect.
    mcp.run()
