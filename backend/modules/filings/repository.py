"""Data-access for the filings module."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.filings.models import Filing


def list_filings(
    db: Session, symbol: str, filing_type: str | None = None
) -> list[Filing]:
    stmt = select(Filing).where(Filing.symbol == symbol.upper())
    if filing_type:
        stmt = stmt.where(func.lower(Filing.filing_type) == filing_type.lower())
    return list(db.scalars(stmt.order_by(Filing.filing_date)))


def latest_filing(
    db: Session, symbol: str, filing_type: str | None = None
) -> Filing | None:
    stmt = select(Filing).where(Filing.symbol == symbol.upper())
    if filing_type:
        stmt = stmt.where(func.lower(Filing.filing_type) == filing_type.lower())
    return db.scalars(stmt.order_by(Filing.filing_date.desc()).limit(1)).first()


def count(db: Session) -> int:
    return db.scalar(select(func.count(Filing.filing_id))) or 0
