"""FastAPI router for the listings module (mounted at /listings)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from modules.listings import repository as repo
from modules.listings.schemas import CompanyOut, SectorOut

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("/companies", response_model=list[CompanyOut])
def get_companies(
    sector: str | None = Query(None, description="Filter by sector"),
    market: str | None = Query(None, description="SET or mai"),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
) -> list[CompanyOut]:
    rows = repo.list_companies(db, sector=sector, market=market, active_only=active_only)
    return [CompanyOut.model_validate(r) for r in rows]


@router.get("/companies/{symbol}", response_model=CompanyOut)
def get_company(symbol: str, db: Session = Depends(get_db)) -> CompanyOut:
    company = repo.get_company(db, symbol)
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company '{symbol}' not found")
    return CompanyOut.model_validate(company)


@router.get("/sectors", response_model=list[SectorOut])
def get_sectors(db: Session = Depends(get_db)) -> list[SectorOut]:
    return [SectorOut(sector=s, company_count=n) for s, n in repo.list_sectors(db)]
