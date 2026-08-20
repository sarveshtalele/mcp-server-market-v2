"""ORM model(s) for the filings module."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Filing(Base):
    """A periodic financial filing for a company (quarter or year)."""

    __tablename__ = "filings"
    __table_args__ = (UniqueConstraint("symbol", "fiscal_period", "filing_type", name="uq_filing"),)

    filing_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("companies.symbol"), nullable=False, index=True)
    filing_type: Mapped[str] = mapped_column(String(24), nullable=False)  # Quarterly|Annual
    fiscal_period: Mapped[str] = mapped_column(String(12), nullable=False)  # 2024Q3
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)

    revenue: Mapped[float] = mapped_column(Float, nullable=False)
    net_profit: Mapped[float] = mapped_column(Float, nullable=False)
    total_assets: Mapped[float] = mapped_column(Float, nullable=False)
    total_liabilities: Mapped[float] = mapped_column(Float, nullable=False)
    total_equity: Mapped[float] = mapped_column(Float, nullable=False)
    operating_cash_flow: Mapped[float] = mapped_column(Float, nullable=False)
    eps: Mapped[float] = mapped_column(Float, nullable=False)
