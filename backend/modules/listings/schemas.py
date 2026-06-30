"""Pydantic response schemas for the listings module."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    company_name: str
    sector: str
    industry: str
    market: str
    listing_date: date
    par_value: float
    shares_outstanding: int
    last_price: float
    market_cap: float
    pe_ratio: float
    pb_ratio: float
    dividend_yield: float
    is_active: bool


class SectorOut(BaseModel):
    sector: str
    company_count: int
