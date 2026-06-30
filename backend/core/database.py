"""SQLAlchemy engine, session factory and declarative Base."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core.config import settings

# `check_same_thread` only needed for SQLite + multi-threaded servers (uvicorn).
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (idempotent).

    Discovering modules imports their packages, which import their models and
    register them on Base.metadata — so every module's tables are created.
    """
    from core.registry import discover_modules

    discover_modules()
    Base.metadata.create_all(bind=engine)
