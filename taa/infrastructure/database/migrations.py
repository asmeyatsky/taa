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
# Migration functions
# ------------------------------------------------------------------

async def _migrate_v2(conn: aiosqlite.Connection) -> None:
    """Add multi-tenant support: organizations table and org_id columns."""
    # Create organizations table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            slug        TEXT NOT NULL UNIQUE,
            plan        TEXT NOT NULL DEFAULT 'free',
            max_users   INTEGER NOT NULL DEFAULT 5,
            is_active   INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Add org_id to existing tables (SQLite requires ALTER TABLE for each column)
    # These use try/except because the column may already exist on a fresh DB
    for table in ("users", "schemas", "mappings", "exports", "audit_log"):
        try:
            await conn.execute(
                f"ALTER TABLE {table} ADD COLUMN org_id TEXT REFERENCES organizations(id) ON DELETE SET NULL"
            )
        except Exception:
            # Column already exists (e.g. fresh database created with v2 schema)
            pass

    # Create indexes for org_id columns
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_org ON users(org_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_schemas_org ON schemas(org_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mappings_org ON mappings(org_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_exports_org ON exports(org_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_org ON audit_log(org_id)"
    )


# ------------------------------------------------------------------
# Migration registry
# ------------------------------------------------------------------

MIGRATIONS: dict[int, callable] = {
    2: _migrate_v2,
}


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
