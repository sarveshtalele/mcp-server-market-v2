"""MCP tools for the analytics module.

A tool-only module: no table, no router. It composes data from the listings and
filings APIs and runs the shared pure functions in ``core.calculations``. This
is the template for "I just want to add a calculation tool".
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from core import calculations as calc
from mcp_server.api_client import DataAPIClient, DataAPIError


def register_tools(mcp: FastMCP, api: DataAPIClient) -> None:
    @mcp.tool()
    async def calc_financial_ratios(
        symbol: str, fiscal_period: str | None = None
    ) -> dict:
        """Compute profitability, leverage, efficiency and valuation ratios.

        Uses the latest quarterly filing unless `fiscal_period` (e.g. '2024Q3').
        """
        try:
            company = await api.get(f"/listings/companies/{symbol.upper()}")
            filings = await api.get(
                f"/filings/{symbol.upper()}", {"filing_type": "Quarterly"}
            )
        except DataAPIError as e:
            return {"error": str(e)}
        if fiscal_period:
            match = [f for f in filings if f["fiscal_period"] == fiscal_period]
            if not match:
                return {"error": f"No quarterly filing for {symbol} {fiscal_period}"}
            filing = match[0]
        else:
            filing = filings[-1]
        return calc.financial_ratios(company, filing)

    @mcp.tool()
    async def calc_revenue_growth(symbol: str) -> dict:
        """Compute QoQ and YoY revenue & net-profit growth from quarterly filings."""
        try:
            filings = await api.get(
                f"/filings/{symbol.upper()}", {"filing_type": "Quarterly"}
            )
        except DataAPIError as e:
            return {"error": str(e)}
        return calc.revenue_growth(filings)

    @mcp.tool()
    async def compare_companies(symbols: list[str]) -> dict:
        """Side-by-side valuation + profitability comparison for several tickers."""
        rows = []
        for sym in symbols:
            try:
                company = await api.get(f"/listings/companies/{sym.upper()}")
                filing = await api.get(
                    f"/filings/{sym.upper()}/latest", {"filing_type": "Quarterly"}
                )
            except DataAPIError as e:
                return {"error": str(e)}
            rows.append({"company": company, "filing": filing})
        return calc.compare_companies(rows)

    @mcp.tool()
    async def sector_ranking(
        sector: str, metric: str = "market_cap", top_n: int = 5
    ) -> dict:
        """Rank companies in a sector by a metric.

        metric: market_cap | pe_ratio | pb_ratio | dividend_yield | last_price.
        """
        try:
            companies = await api.get("/listings/companies", {"sector": sector})
        except DataAPIError as e:
            return {"error": str(e)}
        if not companies:
            return {"error": f"No companies found in sector '{sector}'"}
        return calc.sector_ranking(companies, metric=metric, top_n=top_n)
