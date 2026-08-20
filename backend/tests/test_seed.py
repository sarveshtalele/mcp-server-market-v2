"""SPECS DATA-1 — the synthetic dataset must be frozen and reproducible."""

from __future__ import annotations

from core import seed as seed_module
from core.database import SessionLocal
from modules.filings.models import Filing
from modules.listings.models import Company


def _snapshot() -> list[tuple]:
    with SessionLocal() as db:
        return [
            (c.symbol, c.company_name, c.last_price, c.shares_outstanding, c.market_cap)
            for c in db.query(Company).order_by(Company.symbol).all()
        ]


def test_seed_constants() -> None:
    """DATA-1.2 — changing the seed invalidates every golden fixture."""
    assert seed_module.SEED == 2025


def test_seed_determinism() -> None:
    """DATA-1.1 — reseeding produces identical rows."""
    before = _snapshot()
    seed_module.seed(reset=True)
    assert _snapshot() == before


def test_market_cap_identity() -> None:
    """DATA-1.3 — market cap is price x shares, not an independent number."""
    with SessionLocal() as db:
        companies = db.query(Company).all()
    assert companies, "dataset is empty"
    for company in companies:
        expected = company.last_price * company.shares_outstanding
        assert abs(company.market_cap - expected) <= max(1.0, expected * 1e-6), (
            f"{company.symbol}: market_cap {company.market_cap} != "
            f"{company.last_price} x {company.shares_outstanding}"
        )


def test_shares_outstanding_is_banded_per_company() -> None:
    """DATA-1.3 — a flat share band makes cross-company comparison meaningless."""
    with SessionLocal() as db:
        shares = [c.shares_outstanding for c in db.query(Company).all()]
    assert max(shares) / min(shares) > 10, "share counts look like one flat band"


def test_filings_exist_for_every_company() -> None:
    with SessionLocal() as db:
        symbols = {c.symbol for c in db.query(Company).all()}
        filed = {f.symbol for f in db.query(Filing).all()}
    assert symbols == filed
