"""ORM model(s) for the listings module."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Company(Base):
    """A listed company (e.g. on NYSE / NASDAQ)."""

    __tablename__ = "companies"

    symbol: Mapped[str] = mapped_column(String(12), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(160), nullable=False)
    sector: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    industry: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(8), nullable=False)  # NYSE | NASDAQ
    listing_date: Mapped[date] = mapped_column(Date, nullable=False)

    par_value: Mapped[float] = mapped_column(Float, nullable=False)
    shares_outstanding: Mapped[int] = mapped_column(Integer, nullable=False)
    last_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_cap: Mapped[float] = mapped_column(Float, nullable=False)

    pe_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    pb_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    dividend_yield: Mapped[float] = mapped_column(Float, nullable=False)  # percent
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
