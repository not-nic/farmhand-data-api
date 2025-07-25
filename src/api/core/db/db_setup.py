"""
Python module for initialising the database instance used in the Farmhand Data API.
"""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.api.core.config import settings


def get_engine() -> Engine:
    """
    get the database engine from the URL.
    :return: the database engine
    """
    return create_engine(str(settings.DATABASE_URL), pool_size=10, max_overflow=20)


def _get_db() -> Generator[Session, None, None]:
    """
    Internal generator for DB session management.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


get_db = _get_db
db_session = contextmanager(_get_db)
engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
