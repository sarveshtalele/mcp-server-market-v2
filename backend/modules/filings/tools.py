"""MCP tools for the filings module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core import data
from core.api_tools import DataTool, register_data_tools

# Return annotations include ``dict`` because the error path returns
# ``{"error": ...}``. The SDK derives an output schema from the annotation and
# validates against it, so a bare ``list[dict]`` would turn a missing ticker
# into a schema-validation failure instead of a readable answer.

if TYPE_CHECKING:
    from mcp.server import MCPServer


def get_filings(symbol: str, filing_type: str | None = None) -> list[dict] | dict:
    """Get the filing history for a company. filing_type: 'Quarterly' or 'Annual'."""
    return data.get_filings(symbol, filing_type=filing_type)


def get_latest_filing(symbol: str, filing_type: str | None = None) -> dict:
    """Get the most recent filing for a company. filing_type: 'Quarterly' or 'Annual'."""
    return data.get_latest_filing(symbol, filing_type=filing_type)


TOOLS = [
    DataTool(
        name="get_filings",
        description=("Get the filing history for a company. filing_type: 'Quarterly' or 'Annual'."),
        fn=get_filings,
    ),
    DataTool(
        name="get_latest_filing",
        description=(
            "Get the most recent filing for a company. filing_type: 'Quarterly' or 'Annual'."
        ),
        fn=get_latest_filing,
    ),
]


def register_tools(mcp: MCPServer) -> None:
    register_data_tools(mcp, TOOLS)
