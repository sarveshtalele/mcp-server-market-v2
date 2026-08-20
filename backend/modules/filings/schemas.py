"""Pydantic response schema for the filings module."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class FilingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filing_id: int
    symbol: str
    filing_type: str
    fiscal_period: str
    filing_date: date
    revenue: float
    net_profit: float
    total_assets: float
    total_liabilities: float
    total_equity: float
    operating_cash_flow: float
    eps: float
