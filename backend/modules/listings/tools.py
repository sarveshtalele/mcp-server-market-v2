"""MCP tools for the listings module — declared as API endpoint bindings.

Each tool maps 1:1 to a Data API endpoint (see ENDPOINTS). To add a tool,
add an EndpointTool row; no function body needed for pure data proxies.
"""
from __future__ import annotations

from core.api_tools import EndpointTool, register_endpoint_tools
from mcp_server.api_client import DataAPIClient
from mcp.server.fastmcp import FastMCP

ENDPOINTS = [
    EndpointTool(
        name="get_company",
        description="Get listing details for one company by ticker symbol (e.g. 'AAPL').",
        path="/listings/companies/{symbol}",
        path_params=["symbol"],
    ),
    EndpointTool(
        name="search_companies",
        description="Search listed companies, optionally filtered by sector and/or board (NYSE|NASDAQ).",
        path="/listings/companies",
        query_params=["sector", "market"],
    ),
    EndpointTool(
        name="list_sectors",
        description="List all sectors with the number of companies in each.",
        path="/listings/sectors",
    ),
]


def register_tools(mcp: FastMCP, api: DataAPIClient) -> None:
    register_endpoint_tools(mcp, api, ENDPOINTS)
