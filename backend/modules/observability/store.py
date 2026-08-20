"""Storage for the audit log.

Deliberately a **separate** database from the market data. ``core.seed --reset``
drops and rebuilds every table registered on the market ``Base``; if the audit
rows lived there, reseeding the synthetic dataset would silently destroy the
call history. Different lifecycle, different file.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

_connect_args = (
    {"check_same_thread": False} if settings.observability_database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.observability_database_url,
    connect_args=_connect_args,
    echo=False,
    future=True,
)

ObsSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class ObsBase(DeclarativeBase):
    """Declarative base for observability tables only."""


def get_obs_db() -> Iterator[Session]:
    """FastAPI dependency yielding an observability session."""
    db = ObsSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_obs_db() -> None:
    """Create the audit tables (idempotent)."""
    from modules.observability import models  # noqa: F401  (register on metadata)

    ObsBase.metadata.create_all(bind=engine)
