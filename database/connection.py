"""SQLAlchemy engine/session setup.

Uses DATABASE_URL from config, defaulting to a local SQLite file. Switching to
PostgreSQL later only requires changing DATABASE_URL - no other code changes.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

import config
from logging_config import get_logger

logger = get_logger(__name__)

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(config.DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def _sync_schema() -> None:
    """Add any model columns missing from an already-existing SQLite database.

    `create_all` only creates missing *tables*, not missing *columns* on a
    table that already exists. Since this MVP has no migration framework
    (Alembic is out of scope), new columns added to a model are synced here
    with plain `ALTER TABLE ... ADD COLUMN` statements - safe on SQLite as
    long as the column is nullable or has a default.
    """
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            col_type = column.type.compile(dialect=engine.dialect)
            default_clause = ""
            if column.default is not None and column.default.is_scalar:
                default_clause = f" DEFAULT {column.default.arg!r}"
            with engine.begin() as conn:
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_clause}')
                )
            logger.info("Added missing column %s.%s", table.name, column.name)


def init_db() -> None:
    """Create all tables if they do not already exist, and sync any new columns."""
    import database.models  # noqa: F401  ensures models are registered on Base

    Base.metadata.create_all(bind=engine)
    _sync_schema()

    from database.seed_geo import seed_countries_and_cities

    seed_countries_and_cities()


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session that commits on success and rolls back on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
