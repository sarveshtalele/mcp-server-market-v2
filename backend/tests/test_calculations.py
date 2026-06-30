"""Unit tests for the pure financial calculations (no DB / network)."""
from __future__ import annotations

from core import calculations as calc

COMPANY = {
    "symbol": "TEST",
    "company_name": "Test PCL",
    "sector": "Financials",
    "market_cap": 1_000_000_000.0,
    "last_price": 50.0,
    "pe_ratio": 12.0,
    "pb_ratio": 1.5,
    "dividend_yield": 4.0,
}


def _filing(period: str, revenue: float, net_profit: float) -> dict:
    equity = revenue * 2
    liabilities = equity * 0.5
    return {
        "symbol": "TEST",
        "filing_type": "Quarterly",
        "fiscal_period": period,
        "revenue": revenue,
        "net_profit": net_profit,
        "total_assets": equity + liabilities,
        "total_liabilities": liabilities,
        "total_equity": equity,
        "operating_cash_flow": net_profit * 1.1,
        "eps": net_profit / 1_000_000,
    }


def test_financial_ratios_basic():
    f = _filing("2024Q4", revenue=1000.0, net_profit=200.0)
    r = calc.financial_ratios(COMPANY, f)
    assert r["profitability"]["net_profit_margin_pct"] == 20.0  # 200/1000
    # equity = 2000 -> ROE = 200/2000 = 10%
    assert r["profitability"]["return_on_equity_pct"] == 10.0
    assert r["valuation"]["pe_ratio"] == 12.0


def test_financial_ratios_zero_revenue_is_safe():
    f = _filing("2024Q4", revenue=0.0, net_profit=0.0)
    r = calc.financial_ratios(COMPANY, f)
    assert r["profitability"]["net_profit_margin_pct"] is None  # no divide-by-zero


def test_revenue_growth_qoq_yoy():
    filings = [
        _filing("2023Q1", 100, 10),
        _filing("2023Q2", 110, 11),
        _filing("2023Q3", 120, 12),
        _filing("2023Q4", 130, 13),
        _filing("2024Q1", 200, 20),  # latest; QoQ vs Q4(130), YoY vs 2023Q1(100)
    ]
    g = calc.revenue_growth(filings)
    assert g["latest_period"] == "2024Q1"
    assert round(g["revenue_qoq_pct"], 2) == round((200 - 130) / 130 * 100, 2)
    assert round(g["revenue_yoy_pct"], 2) == 100.0  # 100 -> 200


def test_revenue_growth_needs_two_quarters():
    g = calc.revenue_growth([_filing("2024Q1", 100, 10)])
    assert "error" in g


def test_sector_ranking_orders_and_validates():
    companies = [
        {**COMPANY, "symbol": "A", "market_cap": 3.0},
        {**COMPANY, "symbol": "B", "market_cap": 1.0},
        {**COMPANY, "symbol": "C", "market_cap": 2.0},
    ]
    r = calc.sector_ranking(companies, metric="market_cap", top_n=2)
    assert [x["symbol"] for x in r["ranking"]] == ["A", "C"]  # descending
    # PE is ascending (lower = better)
    r2 = calc.sector_ranking(companies, metric="pe_ratio", top_n=1)
    assert r2["order"] == "ascending"
    # invalid metric
    assert "error" in calc.sector_ranking(companies, metric="bogus")


def test_compare_companies_highlights():
    rows = [
        {"company": {**COMPANY, "symbol": "A", "market_cap": 5.0, "pe_ratio": 20.0},
         "filing": _filing("2024Q4", 1000, 300)},
        {"company": {**COMPANY, "symbol": "B", "market_cap": 9.0, "pe_ratio": 8.0},
         "filing": _filing("2024Q4", 1000, 100)},
    ]
    out = calc.compare_companies(rows)
    assert out["highlights"]["largest_by_market_cap"] == "B"
    assert out["highlights"]["cheapest_by_pe"] == "B"
    assert out["highlights"]["highest_roe"] == "A"  # higher net profit / equity
