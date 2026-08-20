"""In-process data access for MCP tools and resources (decision D-2).

Tools used to reach the data over loopback HTTP to the REST API -- a round trip
from the process to itself. They now call the module repositories directly and
serialise through the same Pydantic schemas the REST routers use, so the JSON a
tool returns is byte-identical to the JSON the equivalent endpoint returns.
``tests/test_rest_parity.py`` asserts exactly that.

Repository imports are deliberately **inside** the functions: modules import
this module, so importing them at module scope would close an import cycle.

Everything here is synchronous. MCP tools that use it are declared as plain
``def`` functions, which the SDK runs on a worker thread -- so blocking
SQLAlchemy calls never occupy the event loop.
"""

from __future__ import annotations

from typing import Any

from core.database import SessionLocal
from core.errors import DataError

__all__ = [
    "DataError",
    "get_company",
    "get_filings",
    "get_latest_filing",
    "list_sectors",
    "search_companies",
]


def _dump(model: Any) -> dict:
    """Serialise a Pydantic model exactly as FastAPI would (dates -> ISO)."""
    return model.model_dump(mode="json")


def get_company(symbol: str) -> dict:
    """One company's listing record. Mirrors GET /listings/companies/{symbol}."""
    from modules.listings import repository as repo
    from modules.listings.schemas import CompanyOut

    with SessionLocal() as db:
        company = repo.get_company(db, symbol)
        if company is None:
            raise DataError(f"Company '{symbol}' not found")
        return _dump(CompanyOut.model_validate(company))


def search_companies(
    sector: str | None = None,
    market: str | None = None,
    active_only: bool = True,
) -> list[dict]:
    """Companies, optionally filtered. Mirrors GET /listings/companies."""
    from modules.listings import repository as repo
    from modules.listings.schemas import CompanyOut

    with SessionLocal() as db:
        rows = repo.list_companies(db, sector=sector, market=market, active_only=active_only)
        return [_dump(CompanyOut.model_validate(r)) for r in rows]


def list_sectors() -> list[dict]:
    """Sectors with company counts. Mirrors GET /listings/sectors."""
    from modules.listings import repository as repo
    from modules.listings.schemas import SectorOut

    with SessionLocal() as db:
        return [_dump(SectorOut(sector=s, company_count=n)) for s, n in repo.list_sectors(db)]


def get_filings(symbol: str, filing_type: str | None = None) -> list[dict]:
    """Filing history. Mirrors GET /filings/{symbol}."""
    from modules.filings import repository as repo
    from modules.filings.schemas import FilingOut

    with SessionLocal() as db:
        rows = repo.list_filings(db, symbol, filing_type=filing_type)
        if not rows:
            raise DataError(f"No filings for '{symbol}'")
        return [_dump(FilingOut.model_validate(r)) for r in rows]


def get_latest_filing(symbol: str, filing_type: str | None = None) -> dict:
    """Most recent filing. Mirrors GET /filings/{symbol}/latest."""
    from modules.filings import repository as repo
    from modules.filings.schemas import FilingOut

    with SessionLocal() as db:
        row = repo.latest_filing(db, symbol, filing_type=filing_type)
        if row is None:
            raise DataError(f"No filings for '{symbol}'")
        return _dump(FilingOut.model_validate(row))
