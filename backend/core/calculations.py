"""Pure financial calculation functions.

No DB or network access here — every function takes plain numbers / dicts and
returns plain numbers / dicts. This keeps the maths testable and lets both the
MCP server and the AG-UI agent reuse identical logic.

All ratios are rounded to 4 decimals; percentages are expressed as percent
values (e.g. 12.34 == 12.34%).
"""
from __future__ import annotations

from typing import Any


def _pct(numerator: float, denominator: float) -> float | None:
    """Return numerator/denominator as a percentage, or None if undefined."""
    if denominator in (0, None):
        return None
    return round((numerator / denominator) * 100, 4)


def _ratio(numerator: float, denominator: float) -> float | None:
    if denominator in (0, None):
        return None
    return round(numerator / denominator, 4)


def financial_ratios(company: dict[str, Any], filing: dict[str, Any]) -> dict[str, Any]:
    """Profitability, leverage and efficiency ratios from one filing + listing.

    Inputs are dicts shaped like CompanyOut / FilingOut.
    """
    revenue = filing["revenue"]
    net_profit = filing["net_profit"]
    assets = filing["total_assets"]
    liabilities = filing["total_liabilities"]
    equity = filing["total_equity"]

    return {
        "symbol": company["symbol"],
        "fiscal_period": filing["fiscal_period"],
        "profitability": {
            "net_profit_margin_pct": _pct(net_profit, revenue),
            "return_on_equity_pct": _pct(net_profit, equity),
            "return_on_assets_pct": _pct(net_profit, assets),
        },
        "leverage": {
            "debt_to_equity": _ratio(liabilities, equity),
            "equity_ratio": _ratio(equity, assets),
            "liabilities_to_assets": _ratio(liabilities, assets),
        },
        "efficiency": {
            "asset_turnover": _ratio(revenue, assets),
            "operating_cash_flow_margin_pct": _pct(
                filing["operating_cash_flow"], revenue
            ),
        },
        "per_share": {
            "eps": round(filing["eps"], 4),
        },
        "valuation": {
            "pe_ratio": company["pe_ratio"],
            "pb_ratio": company["pb_ratio"],
            "dividend_yield_pct": company["dividend_yield"],
        },
    }


def revenue_growth(filings: list[dict[str, Any]]) -> dict[str, Any]:
    """Quarter-over-quarter and year-over-year growth from a filing history.

    `filings` must be quarterly filings; they are sorted by fiscal_period.
    """
    quarterly = sorted(
        (f for f in filings if f["filing_type"] == "Quarterly"),
        key=lambda f: f["fiscal_period"],
    )
    if len(quarterly) < 2:
        return {"error": "Need at least two quarterly filings to compute growth."}

    latest = quarterly[-1]
    prev = quarterly[-2]
    year_ago = quarterly[-5] if len(quarterly) >= 5 else None

    return {
        "symbol": latest["symbol"],
        "latest_period": latest["fiscal_period"],
        "latest_revenue": latest["revenue"],
        "latest_net_profit": latest["net_profit"],
        "revenue_qoq_pct": _pct(latest["revenue"] - prev["revenue"], prev["revenue"]),
        "net_profit_qoq_pct": _pct(
            latest["net_profit"] - prev["net_profit"], prev["net_profit"]
        ),
        "revenue_yoy_pct": (
            _pct(latest["revenue"] - year_ago["revenue"], year_ago["revenue"])
            if year_ago
            else None
        ),
        "net_profit_yoy_pct": (
            _pct(latest["net_profit"] - year_ago["net_profit"], year_ago["net_profit"])
            if year_ago
            else None
        ),
    }


def compare_companies(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Side-by-side valuation snapshot for several companies.

    Each row: {company: CompanyOut-dict, filing: latest FilingOut-dict}.
    """
    table = []
    for row in rows:
        c = row["company"]
        f = row["filing"]
        table.append(
            {
                "symbol": c["symbol"],
                "company_name": c["company_name"],
                "sector": c["sector"],
                "market_cap": c["market_cap"],
                "last_price": c["last_price"],
                "pe_ratio": c["pe_ratio"],
                "pb_ratio": c["pb_ratio"],
                "dividend_yield_pct": c["dividend_yield"],
                "net_profit_margin_pct": _pct(f["net_profit"], f["revenue"]),
                "return_on_equity_pct": _pct(f["net_profit"], f["total_equity"]),
            }
        )

    def _best(key: str, reverse: bool) -> str | None:
        vals = [t for t in table if t.get(key) is not None]
        if not vals:
            return None
        return sorted(vals, key=lambda t: t[key], reverse=reverse)[0]["symbol"]

    return {
        "companies": table,
        "highlights": {
            "largest_by_market_cap": _best("market_cap", True),
            "cheapest_by_pe": _best("pe_ratio", False),
            "highest_roe": _best("return_on_equity_pct", True),
            "highest_dividend_yield": _best("dividend_yield_pct", True),
        },
    }


# Unit label + formatter per metric, so the response is self-describing and
# pre-rounded — every consumer (MCP client, chatbot, etc.) gets the same
# clean value instead of each one formatting a raw huge float differently.
_METRIC_UNITS: dict[str, str] = {
    "market_cap": "USD billions",
    "last_price": "USD",
    "pe_ratio": "ratio",
    "pb_ratio": "ratio",
    "dividend_yield": "percent",
}


def _format_metric_value(metric: str, raw: float) -> float:
    if metric == "market_cap":
        return round(raw / 1e9, 2)
    return round(raw, 2)


def sector_ranking(
    companies: list[dict[str, Any]], metric: str, top_n: int = 5
) -> dict[str, Any]:
    """Rank companies in a sector by a chosen metric (descending)."""
    if metric not in _METRIC_UNITS:
        return {"error": f"metric must be one of {sorted(_METRIC_UNITS)}"}

    # Lower PE / PB is 'better', so ascending for those.
    ascending = metric in {"pe_ratio", "pb_ratio"}
    ranked = sorted(companies, key=lambda c: c[metric], reverse=not ascending)[:top_n]

    return {
        "metric": metric,
        "unit": _METRIC_UNITS[metric],
        "order": "ascending" if ascending else "descending",
        "ranking": [
            {
                "rank": i + 1,
                "symbol": c["symbol"],
                "company_name": c["company_name"],
                "value": _format_metric_value(metric, c[metric]),
            }
            for i, c in enumerate(ranked)
        ],
    }
