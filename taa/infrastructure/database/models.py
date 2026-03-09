"""SQL table definitions for the TAA database.

Raw SQL schemas for SQLite - no ORM dependency required.
Each table has a corresponding create statement and the module
tracks the current schema version for migrations.
"""

from __future__ import annotations

SCHEMA_VERSION = 1

TABLES: dict[str, str] = {
    "schema_version": """
        CREATE TABLE IF NOT EXISTS schema_version (
            id          INTEGER PRIMARY KEY CHECK (id = 1),
            version     INTEGER NOT NULL DEFAULT 1,
            applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            username        TEXT NOT NULL UNIQUE,
            name            TEXT NOT NULL DEFAULT '',
            email           TEXT NOT NULL DEFAULT '',
            role            TEXT NOT NULL DEFAULT 'user',
            hashed_password TEXT NOT NULL,
            disabled        INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
    "schemas": """
        CREATE TABLE IF NOT EXISTS schemas (
            id               TEXT PRIMARY KEY,
            user_id          TEXT,
            content          TEXT NOT NULL,
            format           TEXT NOT NULL DEFAULT 'auto',
            tables_found     INTEGER NOT NULL DEFAULT 0,
            columns_found    INTEGER NOT NULL DEFAULT 0,
            detected_vendor  TEXT,
            vendor_confidence REAL NOT NULL DEFAULT 0.0,
            uploaded_at      TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """,
    "mappings": """
        CREATE TABLE IF NOT EXISTS mappings (
            id               TEXT PRIMARY KEY,
            schema_id        TEXT,
            vendor_table     TEXT NOT NULL,
            vendor_field     TEXT NOT NULL,
            canonical_table  TEXT NOT NULL,
            canonical_field  TEXT NOT NULL,
            confidence       REAL NOT NULL DEFAULT 0.0,
            match_reason     TEXT NOT NULL DEFAULT '',
            created_at       TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (schema_id) REFERENCES schemas(id) ON DELETE CASCADE
        )
    """,
    "exports": """
        CREATE TABLE IF NOT EXISTS exports (
            id              TEXT PRIMARY KEY,
            user_id         TEXT,
            domains         TEXT NOT NULL DEFAULT '[]',
            jurisdiction    TEXT NOT NULL DEFAULT 'SA',
            file_count      INTEGER NOT NULL DEFAULT 0,
            total_size      INTEGER NOT NULL DEFAULT 0,
            status          TEXT NOT NULL DEFAULT 'completed',
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at      TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """,
    "audit_log": """
        CREATE TABLE IF NOT EXISTS audit_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT,
            action          TEXT NOT NULL,
            resource_type   TEXT NOT NULL DEFAULT '',
            resource_id     TEXT,
            details         TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """,
}

INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE INDEX IF NOT EXISTS idx_schemas_user ON schemas(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_schemas_uploaded ON schemas(uploaded_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_mappings_schema ON mappings(schema_id)",
    "CREATE INDEX IF NOT EXISTS idx_exports_user ON exports(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_exports_created ON exports(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action)",
    "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC)",
]
