"""Synthetic seed for the filings module.

Depends on the listings module (companies must exist first — enforced by
ModuleSpec.priority). Generates 8 quarters + one annual filing per company,
using each company's net-margin band from the listings universe.
"""
from __future__ import annotations

import random
from datetime import date

from sqlalchemy import select

from modules.filings.models import Filing
from modules.listings.models import Company
from modules.listings.seed import UNIVERSE

# symbol -> net-margin band (UNIVERSE tuple: 0 sym,1 name,2 sector,3 industry,
# 4 board,5 price_band,6 margin_band,7 div_band)
_MARGIN = {row[0]: row[6] for row in UNIVERSE}

QUARTERS = [
    ("2023Q1", date(2023, 5, 12)),
    ("2023Q2", date(2023, 8, 11)),
    ("2023Q3", date(2023, 11, 10)),
    ("2023Q4", date(2024, 2, 23)),
    ("2024Q1", date(2024, 5, 13)),
    ("2024Q2", date(2024, 8, 12)),
    ("2024Q3", date(2024, 11, 11)),
    ("2024Q4", date(2025, 2, 24)),
]


def _quarters_for(symbol: str, shares: int) -> list[Filing]:
    margin_band = _MARGIN.get(symbol, (0.05, 0.12))
    base_revenue = random.uniform(2_000, 60_000) * 1_000_000
    growth = random.uniform(-0.03, 0.06)
    out: list[Filing] = []
    for i, (period, fdate) in enumerate(QUARTERS):
        revenue = base_revenue * ((1 + growth) ** i) * (1 + 0.05 * random.uniform(-1, 1))
        net_profit = revenue * random.uniform(*margin_band)
        equity = revenue * random.uniform(1.2, 3.0)
        liabilities = equity * random.uniform(0.4, 1.8)
        out.append(
            Filing(
                symbol=symbol,
                filing_type="Quarterly",
                fiscal_period=period,
                filing_date=fdate,
                revenue=round(revenue, 2),
                net_profit=round(net_profit, 2),
                total_assets=round(equity + liabilities, 2),
                total_liabilities=round(liabilities, 2),
                total_equity=round(equity, 2),
                operating_cash_flow=round(net_profit * random.uniform(0.7, 1.6), 2),
                eps=round(net_profit / shares, 4),
            )
        )
    return out


def seed(db) -> None:
    """Insert filings for every company if none exist."""
    if db.scalar(select(Filing).limit(1)) is not None:
        return
    companies = list(db.scalars(select(Company)))
    for c in companies:
        qs = _quarters_for(c.symbol, c.shares_outstanding)
        for f in qs:
            db.add(f)
        fy = [f for f in qs if f.fiscal_period.startswith("2024")]
        db.add(
            Filing(
                symbol=c.symbol,
                filing_type="Annual",
                fiscal_period="2024",
                filing_date=date(2025, 3, 31),
                revenue=round(sum(f.revenue for f in fy), 2),
                net_profit=round(sum(f.net_profit for f in fy), 2),
                total_assets=fy[-1].total_assets,
                total_liabilities=fy[-1].total_liabilities,
                total_equity=fy[-1].total_equity,
                operating_cash_flow=round(sum(f.operating_cash_flow for f in fy), 2),
                eps=round(sum(f.eps for f in fy), 4),
            )
        )
    db.commit()
