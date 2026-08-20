"""MCP prompts for the analytics module.

Prompts are reusable, server-declared workflows a host can trigger in one click.
They deliberately contain no data: they instruct the model which tools and
resources to use, so the answer still comes from live tool results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server import MCPServer


def register_prompts(mcp: MCPServer) -> None:
    @mcp.prompt(
        name="analyze-equity",
        title="Analyze one equity",
        description=(
            "Financial-health memo for a single ticker: profile, latest filing, ratios and growth."
        ),
    )
    def analyze_equity(symbol: str) -> str:
        ticker = symbol.upper()
        return (
            f"Produce a financial-health memo for {ticker} using this server's data "
            f"only.\n\n"
            f"Steps:\n"
            f"1. Read the resource market://companies/{ticker} for the listing profile.\n"
            f"2. Read market://filings/{ticker}/latest for the most recent quarter.\n"
            f"3. Call calc_financial_ratios(symbol='{ticker}') for profitability, "
            f"leverage, efficiency and valuation.\n"
            f"4. Call calc_revenue_growth(symbol='{ticker}') for QoQ and YoY trends.\n\n"
            f"Write: a one-paragraph summary, a table of the key ratios, and an "
            f"explicit list of anything the data does not support. Report only "
            f"figures returned by the tools, in USD. If a call fails, say so "
            f"instead of estimating. This dataset is synthetic."
        )

    @mcp.prompt(
        name="compare-stocks",
        title="Compare several stocks",
        description="Side-by-side valuation and margin benchmark across 2-5 tickers.",
    )
    def compare_stocks(symbols: str) -> str:
        tickers = [s.strip().upper() for s in symbols.replace(",", " ").split() if s.strip()]
        listed = ", ".join(tickers)
        return (
            f"Benchmark these companies against each other using this server's data "
            f"only: {listed}.\n\n"
            f"Steps:\n"
            f"1. Call compare_companies(symbols={tickers!r}) for the side-by-side table.\n"
            f"2. For any company that stands out, call calc_financial_ratios for it.\n\n"
            f"Write: which company leads on valuation, which on profitability, and "
            f"what the comparison cannot tell you. Report only tool-returned figures, "
            f"in USD. This dataset is synthetic."
        )
