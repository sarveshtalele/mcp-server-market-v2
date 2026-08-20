"""Resource and prompt access as *tools*, so they survive the gateway.

Measured behaviour, not an assumption: agentgateway 1.4.1 proxies `tools/*`
faithfully but answers `resources/list`, `resources/templates/list` and
`prompts/list` with empty arrays, and rewrites `ttlMs` to 0 / `cacheScope` to
`private` on list results. Verified with the real binary against this server —
see CLAUDE.md §9.

Every consumer connects through the gateway (invariant #7), so without this
bridge the resource and prompt surface would be unreachable in practice: the
only way to use it would be to point a host straight at the backend, which
takes that host out of the audit log.

The native `market://` resources and the two prompts are still registered and
still correct — a host that speaks to the server directly gets them, and they
are what the conformance tests exercise. These tools are the governed path to
the same data, not a replacement for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core import data
from core.errors import DataError

if TYPE_CHECKING:
    from mcp.server import MCPServer

RESOURCE_TEMPLATES = (
    "market://companies",
    "market://sectors",
    "market://companies/{symbol}",
    "market://filings/{symbol}/latest",
    "market://filings/{symbol}/{period}",
)


def _resolve(uri: str) -> dict | list[dict]:
    """Resolve a market:// URI to the same payload the resource returns."""
    if not uri.startswith("market://"):
        raise DataError(f"Not a market resource URI: {uri!r}")

    path = uri[len("market://") :].strip("/")
    parts = [p for p in path.split("/") if p]

    # Reject traversal explicitly. The SDK enforces this for real resources;
    # this tool is a separate entry point and needs its own guard.
    if any(p in ("..", ".") for p in parts):
        raise DataError(f"Invalid resource URI: {uri!r}")

    match parts:
        case ["companies"]:
            return data.search_companies()
        case ["sectors"]:
            return data.list_sectors()
        case ["companies", symbol]:
            return data.get_company(symbol)
        case ["filings", symbol, "latest"]:
            return data.get_latest_filing(symbol, filing_type="Quarterly")
        case ["filings", symbol, period]:
            for filing in data.get_filings(symbol, filing_type="Quarterly"):
                if filing["fiscal_period"].upper() == period.upper():
                    return filing
            raise DataError(f"No quarterly filing for {symbol.upper()} {period}")
        case _:
            raise DataError(f"Unknown resource URI: {uri!r}")


def register_tools(mcp: MCPServer) -> None:
    @mcp.tool()
    def list_market_resources() -> dict:
        """List the market:// resource URIs this server can serve."""
        return {
            "templates": list(RESOURCE_TEMPLATES),
            "note": (
                "Read one with read_market_resource(uri). These mirror the "
                "server's native MCP resources, which some gateways do not "
                "proxy."
            ),
        }

    @mcp.tool()
    def read_market_resource(uri: str) -> dict | list[dict]:
        """Read a market:// resource, e.g. 'market://companies/AAPL'.

        Accepts: market://companies, market://sectors,
        market://companies/{symbol}, market://filings/{symbol}/latest,
        market://filings/{symbol}/{period}.
        """
        try:
            return _resolve(uri)
        except DataError as exc:
            return {"error": str(exc)}
