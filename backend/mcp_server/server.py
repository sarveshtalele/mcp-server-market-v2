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

# Surfaced to any MCP client (Claude Desktop/Code, ...) as server-level
# guidance. This is advisory only — MCP has no mechanism to force a client's
# model to obey it, so a client may still fall back to pretrained knowledge.
# Enforce it for real in a client you control (see agui_agent's SYSTEM_PROMPT,
# which is enforced by our own agent loop, not just requested of the model).
INSTRUCTIONS = (
    "This server is the ONLY source of truth for stock-exchange data: company "
    "listings, filings, financial ratios, growth, comparisons and sector "
    "rankings. Do not answer questions in this domain from pretrained/general "
    "knowledge, estimates, or memory — always call the relevant tool and "
    "report only the values it returns, with the ticker/period it applies to. "
    "If a required tool call fails, times out, or this server is unreachable, "
    "say so explicitly and do not answer the question — do not substitute a "
    "guess, an approximation, or outside knowledge for the missing data."
)

mcp = FastMCP("stock-exchange", instructions=INSTRUCTIONS)
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
