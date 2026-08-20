"""MCP resources for the listings module.

Resources let a host attach market data straight into a prompt without spending
a tool-calling round trip. They return exactly the same payload as the
equivalent tool, so nothing can drift between the two surfaces.

Note on scope: resources are consumed by MCP *hosts* (Claude Desktop, Claude
Code, IDEs). This project's own web chat runs an OpenAI function-calling loop,
which has no concept of resources -- adding these does not change the web UI.
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
        "market://companies",
        name="companies",
        description="Every listed company with price, market cap and valuation ratios.",
        mime_type="application/json",
    )
    def all_companies() -> list[dict]:
        return data.search_companies()

    @mcp.resource(
        "market://sectors",
        name="sectors",
        description="All sectors with the number of listed companies in each.",
        mime_type="application/json",
    )
    def all_sectors() -> list[dict]:
        return data.list_sectors()

    @mcp.resource(
        "market://companies/{symbol}",
        name="company",
        description="Listing profile for one company, by ticker symbol.",
        mime_type="application/json",
    )
    def company(symbol: str) -> dict:
        # Unknown resources must surface as Invalid params (-32602) under the
        # 2026-07-28 revision; the SDK maps a ValueError to that code.
        try:
            return data.get_company(symbol)
        except DataError as exc:
            raise _not_found(str(exc)) from exc
