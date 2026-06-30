"""MCP tools for the filings module — declared as API endpoint bindings."""
from __future__ import annotations

from core.api_tools import EndpointTool, register_endpoint_tools
from mcp_server.api_client import DataAPIClient
from mcp.server.fastmcp import FastMCP

ENDPOINTS = [
    EndpointTool(
        name="get_filings",
        description="Get the filing history for a company. filing_type: 'Quarterly' or 'Annual'.",
        path="/filings/{symbol}",
        path_params=["symbol"],
        query_params=["filing_type"],
    ),
    EndpointTool(
        name="get_latest_filing",
        description="Get the most recent filing for a company. filing_type: 'Quarterly' or 'Annual'.",
        path="/filings/{symbol}/latest",
        path_params=["symbol"],
        query_params=["filing_type"],
    ),
]


def register_tools(mcp: FastMCP, api: DataAPIClient) -> None:
    register_endpoint_tools(mcp, api, ENDPOINTS)
