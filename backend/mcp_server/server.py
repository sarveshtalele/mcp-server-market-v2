"""MCP server (FastMCP, stdio transport).

Tools are contributed by modules: every module that defines `register_tools`
gets called with the FastMCP instance and a shared Data API client. Adding a
module is enough to expose its tools here — no change to this file.

Run standalone for Claude Desktop / Claude Code:
    python -m mcp_server.server
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core.registry import discover_modules
from mcp_server.api_client import DataAPIClient

mcp = FastMCP("stock-exchange")
api = DataAPIClient()

# Register tools from every module that provides them.
for spec in discover_modules():
    if spec.register_tools is not None:
        spec.register_tools(mcp, api)


if __name__ == "__main__":
    # Default transport is stdio — the form Claude Desktop / Code expect.
    mcp.run()
