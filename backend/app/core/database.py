"""Database engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Parent class for every database table."""


settings = get_settings()

# pool_pre_ping checks a connection is alive before using it, so a database
# restart does not break the first request afterwards.
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_database_session() -> Generator[Session, None, None]:
    """Give one request its own database session and close it afterwards."""
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()
