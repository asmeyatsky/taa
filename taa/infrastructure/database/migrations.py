"""Simple version-based migration system for TAA SQLite database.

Migrations are plain functions registered in ``MIGRATIONS`` dict,
keyed by the target version number.  The migration runner applies
them in order, updating the ``schema_version`` table after each step.
"""

from __future__ import annotations

import logging

import aiosqlite

from taa.infrastructure.database import models as _models

logger = logging.getLogger(__name__)


async def _get_current_version(conn: aiosqlite.Connection) -> int:
    """Read the current schema version from the database."""
    cursor = await conn.execute(
        "SELECT version FROM schema_version WHERE id = 1"
    )
    row = await cursor.fetchone()
    if row is None:
        return 0
    return int(row[0])


async def _set_version(conn: aiosqlite.Connection, version: int) -> None:
    """Update the stored schema version."""
    await conn.execute(
        "UPDATE schema_version SET version = ?, applied_at = datetime('now') WHERE id = 1",
        (version,),
    )
    await conn.commit()


# ------------------------------------------------------------------
# Migration registry
#
# Each entry maps a target version to an async callable that receives
# the aiosqlite connection.  The callable must NOT commit -- the runner
# handles commits.  Add new migrations by appending to this dict.
# ------------------------------------------------------------------

MIGRATIONS: dict[int, callable] = {
    # Example for future use:
    # 2: _migrate_v2,
}


async def _migrate_v2_example(conn: aiosqlite.Connection) -> None:  # pragma: no cover
    """Example migration: add a ``metadata`` column to schemas."""
    await conn.execute(
        "ALTER TABLE schemas ADD COLUMN metadata TEXT DEFAULT '{}'"
    )


async def apply_migrations(conn: aiosqlite.Connection) -> None:
    """Apply all pending migrations in order.

    Compares the stored version with ``_models.SCHEMA_VERSION`` from models.py
    and executes each registered migration step sequentially.
    """
    current = await _get_current_version(conn)

    if current >= _models.SCHEMA_VERSION:
        return

    for target_version in sorted(MIGRATIONS.keys()):
        if target_version <= current:
            continue
        if target_version > _models.SCHEMA_VERSION:
            break

        logger.info("Applying migration to version %d ...", target_version)
        migration_fn = MIGRATIONS[target_version]
        await migration_fn(conn)
        await conn.commit()
        await _set_version(conn, target_version)
        logger.info("Migration to version %d complete", target_version)

    # Ensure the version is set even when there are no registered
    # migrations (initial bootstrapping).
    final = await _get_current_version(conn)
    if final < _models.SCHEMA_VERSION:
        await _set_version(conn, _models.SCHEMA_VERSION)
