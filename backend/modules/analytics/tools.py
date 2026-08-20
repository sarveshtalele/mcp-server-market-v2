"""MCP tools for the analytics module.

A tool-only module: no table, no router. It composes data from the listings and
filings repositories and runs the shared pure functions in ``core.calculations``.
This is the template for "I just want to add a calculation tool".

Most tools here are plain ``def`` -- the SDK runs them on a worker thread, so
their blocking database work never occupies the event loop. ``compare_companies``
is ``async`` because it reports progress per ticker, which requires awaiting the
request context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio.to_thread
from mcp.server.mcpserver import Context

from core import calculations as calc
from core import data
from core.errors import DataError

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_tools(mcp: MCPServer) -> None:
    @mcp.tool()
    def calc_financial_ratios(symbol: str, fiscal_period: str | None = None) -> dict:
        """Compute profitability, leverage, efficiency and valuation ratios.

        Uses the latest quarterly filing unless `fiscal_period` (e.g. '2024Q3').
        """
        try:
            company = data.get_company(symbol)
            filings = data.get_filings(symbol, filing_type="Quarterly")
        except DataError as exc:
            return {"error": str(exc)}
        if fiscal_period:
            match = [f for f in filings if f["fiscal_period"] == fiscal_period]
            if not match:
                return {"error": f"No quarterly filing for {symbol} {fiscal_period}"}
            filing = match[0]
        else:
            filing = filings[-1]
        return calc.financial_ratios(company, filing)

    @mcp.tool()
    def calc_revenue_growth(symbol: str) -> dict:
        """Compute QoQ and YoY revenue & net-profit growth from quarterly filings."""
        try:
            filings = data.get_filings(symbol, filing_type="Quarterly")
        except DataError as exc:
            return {"error": str(exc)}
        return calc.revenue_growth(filings)

    @mcp.tool()
    async def compare_companies(symbols: list[str], ctx: Context) -> dict:
        """Side-by-side valuation + profitability comparison for several tickers."""
        rows = []
        total = len(symbols)
        for index, sym in enumerate(symbols, start=1):
            try:
                company = await anyio.to_thread.run_sync(data.get_company, sym)
                filing = await anyio.to_thread.run_sync(
                    lambda s=sym: data.get_latest_filing(s, filing_type="Quarterly")
                )
            except DataError as exc:
                return {"error": str(exc)}
            rows.append({"company": company, "filing": filing})
            # Progress flows on this request's own response stream. It is only
            # emitted when the client opted in with a progressToken.
            await ctx.report_progress(index, total, f"{sym.upper()} ({index}/{total})")
        return calc.compare_companies(rows)

    @mcp.tool()
    def sector_ranking(sector: str, metric: str = "market_cap", top_n: int = 5) -> dict:
        """Rank companies in a sector by a metric.

        metric: market_cap | pe_ratio | pb_ratio | dividend_yield | last_price.
        """
        try:
            companies = data.search_companies(sector=sector)
        except DataError as exc:
            return {"error": str(exc)}
        if not companies:
            return {"error": f"No companies found in sector '{sector}'"}
        return calc.sector_ranking(companies, metric=metric, top_n=top_n)
