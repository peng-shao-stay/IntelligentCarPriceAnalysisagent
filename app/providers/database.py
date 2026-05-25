"""
PostgreSQL-based DatabaseProvider implementation.

Thin wrapper around SQLAlchemy SessionLocal for session lifecycle management.
"""

from __future__ import annotations

from app.core.logging import logger
from app.db.database import SessionLocal
from app.providers.base import DatabaseProvider


class PostgresDatabaseProvider(DatabaseProvider):
    """Database provider backed by PostgreSQL via SQLAlchemy."""

    def create_session(self):
        logger.debug("[PostgresDatabaseProvider] Creating DB session")
        return SessionLocal()

    def close_session(self, session) -> None:
        if session is None:
            return
        try:
            session.close()
            logger.debug("[PostgresDatabaseProvider] DB session closed")
        except Exception:
            logger.exception("[PostgresDatabaseProvider] Error closing DB session")
