"""MCP tools for the listings module.

Each tool is a typed function over ``core.data`` (decision D-2: repositories are
called in-process, not over loopback HTTP). To add a tool, write the function and
add a ``DataTool`` row -- nothing else in the project changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core import data
from core.api_tools import DataTool, register_data_tools
from modules.listings import bridge

# Return annotations include ``dict`` because the error path returns
# ``{"error": ...}``. The SDK derives an output schema from the annotation and
# validates against it, so a bare ``list[dict]`` would turn a missing ticker
# into a schema-validation failure instead of a readable answer.

if TYPE_CHECKING:
    from mcp.server import MCPServer


def get_company(symbol: str) -> dict:
    """Get listing details for one company by ticker symbol (e.g. 'AAPL')."""
    return data.get_company(symbol)


def search_companies(sector: str | None = None, market: str | None = None) -> list[dict] | dict:
    """Search listed companies, optionally filtered by sector and/or board (NYSE|NASDAQ)."""
    return data.search_companies(sector=sector, market=market)


def list_sectors() -> list[dict] | dict:
    """List all sectors with the number of companies in each."""
    return data.list_sectors()


TOOLS = [
    DataTool(
        name="get_company",
        description="Get listing details for one company by ticker symbol (e.g. 'AAPL').",
        fn=get_company,
    ),
    DataTool(
        name="search_companies",
        description=(
            "Search listed companies, optionally filtered by sector and/or board (NYSE|NASDAQ)."
        ),
        fn=search_companies,
    ),
    DataTool(
        name="list_sectors",
        description="List all sectors with the number of companies in each.",
        fn=list_sectors,
    ),
]


def register_tools(mcp: MCPServer) -> None:
    register_data_tools(mcp, TOOLS)
    # Resource access as tools, because the gateway does not proxy resources.
    # See modules/listings/bridge.py for the measured behaviour behind this.
    bridge.register_tools(mcp)
