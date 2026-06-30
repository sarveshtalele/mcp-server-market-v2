"""FastAPI router for the filings module (mounted at /filings)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.database import get_db
from modules.filings import repository as repo
from modules.filings.schemas import FilingOut

router = APIRouter(prefix="/filings", tags=["filings"])


@router.get("/{symbol}", response_model=list[FilingOut])
def get_filings(
    symbol: str,
    filing_type: str | None = Query(None, description="Quarterly or Annual"),
    db: Session = Depends(get_db),
) -> list[FilingOut]:
    rows = repo.list_filings(db, symbol, filing_type=filing_type)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No filings for '{symbol}'")
    return [FilingOut.model_validate(r) for r in rows]


@router.get("/{symbol}/latest", response_model=FilingOut)
def get_latest_filing(
    symbol: str,
    filing_type: str | None = Query(None, description="Quarterly or Annual"),
    db: Session = Depends(get_db),
) -> FilingOut:
    row = repo.latest_filing(db, symbol, filing_type=filing_type)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No filings for '{symbol}'")
    return FilingOut.model_validate(row)
