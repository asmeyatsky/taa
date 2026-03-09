"""Database connection manager with async SQLite.

Auto-creates tables on first run and applies migrations.
Supports fallback: if the database is unavailable, callers can
check ``is_available`` and fall back to in-memory state.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import aiosqlite

from taa.infrastructure.database.models import TABLES, INDEXES, SCHEMA_VERSION

logger = logging.getLogger(__name__)

# Default database URL from environment
_DEFAULT_DB_URL = "sqlite:///./taa.db"


def _parse_sqlite_url(url: str) -> str:
    """Convert a ``sqlite:///path`` URL to a plain file path.

    Special case: ``:memory:`` returns ``:memory:``.
    """
    if url == ":memory:" or url == "sqlite:///:memory:":
        return ":memory:"
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    if url.startswith("sqlite://"):
        return url[len("sqlite://"):]
    return url


class DatabaseManager:
    """Manages the async SQLite database connection lifecycle."""

    def __init__(self, url: str | None = None) -> None:
        raw_url = url or os.getenv("TAA_DATABASE_URL", _DEFAULT_DB_URL)
        self._db_path = _parse_sqlite_url(raw_url)
        self._connection: aiosqlite.Connection | None = None
        self._available = False

    @property
    def is_available(self) -> bool:
        """True when the database is connected and initialised."""
        return self._available

    @property
    def db_path(self) -> str:
        return self._db_path

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open the connection, create tables, and run migrations."""
        try:
            self._connection = await aiosqlite.connect(self._db_path)
            self._connection.row_factory = aiosqlite.Row
            await self._connection.execute("PRAGMA journal_mode=WAL")
            await self._connection.execute("PRAGMA foreign_keys=ON")
            await self._create_tables()
            await self._apply_migrations()
            self._available = True
            logger.info("Database initialised at %s", self._db_path)
        except Exception:
            logger.exception("Failed to initialise database – falling back to in-memory")
            self._available = False

    async def close(self) -> None:
        """Gracefully close the database connection."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            self._available = False
            logger.info("Database connection closed")

    def get_connection(self) -> aiosqlite.Connection:
        """Return the active connection.

        Raises ``RuntimeError`` if the database has not been initialised.
        """
        if self._connection is None or not self._available:
            raise RuntimeError("Database is not available")
        return self._connection

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_tables(self) -> None:
        """Execute all CREATE TABLE statements and indexes."""
        assert self._connection is not None
        for table_sql in TABLES.values():
            await self._connection.execute(table_sql)
        for index_sql in INDEXES:
            await self._connection.execute(index_sql)
        await self._connection.commit()

        # Seed schema version row if missing
        cursor = await self._connection.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        )
        row = await cursor.fetchone()
        if row is None:
            await self._connection.execute(
                "INSERT INTO schema_version (id, version) VALUES (1, ?)",
                (SCHEMA_VERSION,),
            )
            await self._connection.commit()

    async def _apply_migrations(self) -> None:
        """Run any pending migrations."""
        from taa.infrastructure.database.migrations import apply_migrations

        assert self._connection is not None
        await apply_migrations(self._connection)
