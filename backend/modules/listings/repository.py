"""Data-access for the listings module (all company queries live here)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.listings.models import Company


def list_companies(
    db: Session,
    sector: str | None = None,
    market: str | None = None,
    active_only: bool = True,
) -> list[Company]:
    stmt = select(Company)
    if sector:
        stmt = stmt.where(func.lower(Company.sector) == sector.lower())
    if market:
        stmt = stmt.where(func.lower(Company.market) == market.lower())
    if active_only:
        stmt = stmt.where(Company.is_active.is_(True))
    return list(db.scalars(stmt.order_by(Company.market_cap.desc())))


def get_company(db: Session, symbol: str) -> Company | None:
    return db.get(Company, symbol.upper())


def list_sectors(db: Session) -> list[tuple[str, int]]:
    stmt = (
        select(Company.sector, func.count(Company.symbol))
        .group_by(Company.sector)
        .order_by(func.count(Company.symbol).desc())
    )
    return [(row[0], row[1]) for row in db.execute(stmt)]


def count(db: Session) -> int:
    return db.scalar(select(func.count(Company.symbol))) or 0
