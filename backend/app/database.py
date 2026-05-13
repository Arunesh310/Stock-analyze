"""SQLAlchemy database setup (sync engine, works with SQLite or Postgres)."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()

_is_sqlite = _settings.database_url.startswith("sqlite")

connect_args = {"check_same_thread": False} if _is_sqlite else {}

# Cloud Postgres (Neon, Supabase, etc.) on free tier auto-suspends inactive
# compute after a few minutes. ``pool_pre_ping`` quietly drops the dead
# connection and reconnects; ``pool_recycle`` proactively rotates them every
# 5 min so we never hand a half-dead connection to a request. Pool size is
# kept conservative to respect free-tier connection limits.
engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "connect_args": connect_args,
}
if not _is_sqlite:
    engine_kwargs.update(
        pool_size=5,
        max_overflow=10,
        pool_recycle=300,
    )

engine = create_engine(_settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def init_db() -> None:
    """Create tables for any models registered on Base."""
    # Import models so they are registered with Base.metadata
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Iterator[Session]:
    """Context-manager helper for use outside FastAPI dependency injection."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
