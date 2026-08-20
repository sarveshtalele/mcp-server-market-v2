"""MCP resources for the filings module.

Lets a host attach a balance sheet / income statement directly to a prompt
instead of spending a tool-calling round trip on it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core import data
from core.errors import DataError

if TYPE_CHECKING:
    from mcp.server import MCPServer


from mcp import MCPError

_INVALID_PARAMS = -32602


def _not_found(message: str) -> MCPError:
    """Resource-not-found is Invalid params (-32602) in this revision.

    It moved from -32002 in 2026-07-28 to align with JSON-RPC. A bare
    ValueError would surface as -32603 Internal error, which is wrong.
    """
    return MCPError(code=_INVALID_PARAMS, message=message)


def register_resources(mcp: MCPServer) -> None:
    @mcp.resource(
        "market://filings/{symbol}/latest",
        name="latest_filing",
        description="Most recent quarterly filing for a company.",
        mime_type="application/json",
    )
    def latest(symbol: str) -> dict:
        try:
            return data.get_latest_filing(symbol, filing_type="Quarterly")
        except DataError as exc:
            raise _not_found(str(exc)) from exc

    @mcp.resource(
        "market://filings/{symbol}/{period}",
        name="filing_for_period",
        description="Filing for one fiscal period, e.g. 2024Q3.",
        mime_type="application/json",
    )
    def for_period(symbol: str, period: str) -> dict:
        try:
            filings = data.get_filings(symbol, filing_type="Quarterly")
        except DataError as exc:
            raise _not_found(str(exc)) from exc
        for filing in filings:
            if filing["fiscal_period"].upper() == period.upper():
                return filing
        raise _not_found(f"No quarterly filing for {symbol.upper()} {period}")
