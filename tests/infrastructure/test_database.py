"""Tests for the SQLite database backend.

Uses in-memory SQLite (`:memory:`) for full test isolation --
no filesystem state persists between tests.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import pytest_asyncio

from taa.infrastructure.database.connection import DatabaseManager, _parse_sqlite_url
from taa.infrastructure.database.models import SCHEMA_VERSION, TABLES, INDEXES
from taa.infrastructure.database.migrations import (
    apply_migrations,
    _get_current_version,
    _set_version,
    MIGRATIONS,
)
from taa.infrastructure.database.repositories import (
    SQLiteUserRepository,
    SQLiteSchemaRepository,
    SQLiteMappingRepository,
    SQLiteExportRepository,
    SQLiteAuditRepository,
)


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest_asyncio.fixture
async def db():
    """Provide a fresh in-memory database for each test."""
    manager = DatabaseManager(url=":memory:")
    await manager.initialize()
    assert manager.is_available
    yield manager
    await manager.close()


@pytest_asyncio.fixture
async def user_repo(db: DatabaseManager):
    return SQLiteUserRepository(db)


@pytest_asyncio.fixture
async def schema_repo(db: DatabaseManager):
    return SQLiteSchemaRepository(db)


@pytest_asyncio.fixture
async def mapping_repo(db: DatabaseManager):
    return SQLiteMappingRepository(db)


@pytest_asyncio.fixture
async def export_repo(db: DatabaseManager):
    return SQLiteExportRepository(db)


@pytest_asyncio.fixture
async def audit_repo(db: DatabaseManager):
    return SQLiteAuditRepository(db)


# ------------------------------------------------------------------
# Connection manager tests
# ------------------------------------------------------------------

class TestDatabaseManager:
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, db: DatabaseManager):
        conn = db.get_connection()
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        table_names = {row[0] for row in rows}

        for expected in ("users", "schemas", "mappings", "exports", "audit_log", "schema_version"):
            assert expected in table_names, f"Table {expected} not created"

    @pytest.mark.asyncio
    async def test_schema_version_is_set(self, db: DatabaseManager):
        conn = db.get_connection()
        cursor = await conn.execute("SELECT version FROM schema_version WHERE id = 1")
        row = await cursor.fetchone()
        assert row is not None
        assert row[0] == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self, db: DatabaseManager):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row[0] == 1

    @pytest.mark.asyncio
    async def test_close_makes_unavailable(self):
        manager = DatabaseManager(url=":memory:")
        await manager.initialize()
        assert manager.is_available
        await manager.close()
        assert not manager.is_available

    @pytest.mark.asyncio
    async def test_get_connection_raises_when_closed(self):
        manager = DatabaseManager(url=":memory:")
        with pytest.raises(RuntimeError, match="not available"):
            manager.get_connection()

    @pytest.mark.asyncio
    async def test_is_available_false_before_init(self):
        manager = DatabaseManager(url=":memory:")
        assert not manager.is_available

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, db: DatabaseManager):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        # In-memory databases use 'memory' journal mode, not WAL
        assert row[0] in ("wal", "memory")


class TestParseUrl:
    def test_memory(self):
        assert _parse_sqlite_url(":memory:") == ":memory:"

    def test_sqlite_memory(self):
        assert _parse_sqlite_url("sqlite:///:memory:") == ":memory:"

    def test_sqlite_file(self):
        assert _parse_sqlite_url("sqlite:///./taa.db") == "./taa.db"

    def test_sqlite_absolute(self):
        assert _parse_sqlite_url("sqlite:////data/taa.db") == "/data/taa.db"

    def test_plain_path(self):
        assert _parse_sqlite_url("./my.db") == "./my.db"


# ------------------------------------------------------------------
# Migration tests
# ------------------------------------------------------------------

class TestMigrations:
    @pytest.mark.asyncio
    async def test_current_version_matches(self, db: DatabaseManager):
        conn = db.get_connection()
        version = await _get_current_version(conn)
        assert version == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_set_version(self, db: DatabaseManager):
        conn = db.get_connection()
        await _set_version(conn, 99)
        version = await _get_current_version(conn)
        assert version == 99

    @pytest.mark.asyncio
    async def test_apply_migrations_noop_when_current(self, db: DatabaseManager):
        conn = db.get_connection()
        # Should not raise
        await apply_migrations(conn)
        version = await _get_current_version(conn)
        assert version == SCHEMA_VERSION

    @pytest.mark.asyncio
    async def test_apply_custom_migration(self, db: DatabaseManager):
        """Register a fake migration at version SCHEMA_VERSION+1 and apply it."""
        conn = db.get_connection()

        applied = []

        async def fake_migration(c):
            applied.append(True)
            await c.execute(
                "CREATE TABLE IF NOT EXISTS _test_migration (id INTEGER PRIMARY KEY)"
            )

        target = SCHEMA_VERSION + 1
        original_migrations = dict(MIGRATIONS)
        try:
            MIGRATIONS[target] = fake_migration
            # Pretend current schema version target is higher
            from taa.infrastructure.database import models as m
            orig_version = m.SCHEMA_VERSION
            m.SCHEMA_VERSION = target

            await apply_migrations(conn)
            assert len(applied) == 1

            # Verify the table was created
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='_test_migration'"
            )
            row = await cursor.fetchone()
            assert row is not None

            version = await _get_current_version(conn)
            assert version == target
        finally:
            MIGRATIONS.clear()
            MIGRATIONS.update(original_migrations)
            m.SCHEMA_VERSION = orig_version


# ------------------------------------------------------------------
# UserRepository tests
# ------------------------------------------------------------------

class TestUserRepository:
    @pytest.mark.asyncio
    async def test_create_and_get(self, user_repo: SQLiteUserRepository):
        user = await user_repo.create({
            "id": "u1",
            "username": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "role": "user",
            "hashed_password": "hashed123",
        })
        assert user["id"] == "u1"
        assert user["username"] == "testuser"

        fetched = await user_repo.get_by_username("testuser")
        assert fetched is not None
        assert fetched["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repo: SQLiteUserRepository):
        await user_repo.create({
            "id": "u2",
            "username": "user2",
            "hashed_password": "h",
        })
        fetched = await user_repo.get_by_id("u2")
        assert fetched is not None
        assert fetched["username"] == "user2"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, user_repo: SQLiteUserRepository):
        assert await user_repo.get_by_username("nobody") is None
        assert await user_repo.get_by_id("no-id") is None

    @pytest.mark.asyncio
    async def test_update(self, user_repo: SQLiteUserRepository):
        await user_repo.create({
            "id": "u3",
            "username": "updatable",
            "name": "Before",
            "hashed_password": "h",
        })
        updated = await user_repo.update("u3", {"name": "After", "role": "admin"})
        assert updated is not None
        assert updated["name"] == "After"
        assert updated["role"] == "admin"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, user_repo: SQLiteUserRepository):
        result = await user_repo.update("nope", {"name": "X"})
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, user_repo: SQLiteUserRepository):
        await user_repo.create({"id": "a", "username": "alice", "hashed_password": "h"})
        await user_repo.create({"id": "b", "username": "bob", "hashed_password": "h"})
        users = await user_repo.list_all()
        assert len(users) == 2
        usernames = {u["username"] for u in users}
        assert usernames == {"alice", "bob"}

    @pytest.mark.asyncio
    async def test_delete(self, user_repo: SQLiteUserRepository):
        await user_repo.create({"id": "d1", "username": "deleteme", "hashed_password": "h"})
        assert await user_repo.delete("d1") is True
        assert await user_repo.get_by_id("d1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, user_repo: SQLiteUserRepository):
        assert await user_repo.delete("nope") is False

    @pytest.mark.asyncio
    async def test_unique_username_constraint(self, user_repo: SQLiteUserRepository):
        await user_repo.create({"id": "u1", "username": "unique", "hashed_password": "h"})
        with pytest.raises(Exception):
            await user_repo.create({"id": "u2", "username": "unique", "hashed_password": "h"})

    @pytest.mark.asyncio
    async def test_auto_generates_id(self, user_repo: SQLiteUserRepository):
        user = await user_repo.create({"username": "auto_id", "hashed_password": "h"})
        assert user["id"] is not None
        assert len(user["id"]) > 0


# ------------------------------------------------------------------
# SchemaRepository tests
# ------------------------------------------------------------------

class TestSchemaRepository:
    @pytest.mark.asyncio
    async def test_save_and_get(self, schema_repo: SQLiteSchemaRepository):
        saved = await schema_repo.save({
            "id": "s1",
            "content": "CREATE TABLE foo (id INT);",
            "format": "sql",
            "tables_found": 1,
            "columns_found": 1,
            "detected_vendor": "amdocs",
            "vendor_confidence": 0.85,
        })
        assert saved["id"] == "s1"

        fetched = await schema_repo.get_by_id("s1")
        assert fetched is not None
        assert fetched["format"] == "sql"
        assert fetched["tables_found"] == 1
        assert fetched["vendor_confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_list_all_ordered(self, schema_repo: SQLiteSchemaRepository):
        await schema_repo.save({"id": "s1", "content": "a"})
        await schema_repo.save({"id": "s2", "content": "b"})
        await schema_repo.save({"id": "s3", "content": "c"})

        schemas = await schema_repo.list_all(limit=2)
        assert len(schemas) == 2

    @pytest.mark.asyncio
    async def test_delete(self, schema_repo: SQLiteSchemaRepository):
        await schema_repo.save({"id": "s_del", "content": "x"})
        assert await schema_repo.delete("s_del") is True
        assert await schema_repo.get_by_id("s_del") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, schema_repo: SQLiteSchemaRepository):
        assert await schema_repo.delete("nope") is False

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, schema_repo: SQLiteSchemaRepository):
        assert await schema_repo.get_by_id("nope") is None


# ------------------------------------------------------------------
# MappingRepository tests
# ------------------------------------------------------------------

class TestMappingRepository:
    @pytest.mark.asyncio
    async def test_save_and_get_by_schema(
        self, mapping_repo: SQLiteMappingRepository, schema_repo: SQLiteSchemaRepository,
    ):
        await schema_repo.save({"id": "s1", "content": "x"})

        await mapping_repo.save({
            "id": "m1",
            "schema_id": "s1",
            "vendor_table": "CM_SUB",
            "vendor_field": "SUB_ID",
            "canonical_table": "subscriber_profile",
            "canonical_field": "subscriber_id",
            "confidence": 0.95,
            "match_reason": "exact",
        })
        await mapping_repo.save({
            "id": "m2",
            "schema_id": "s1",
            "vendor_table": "CM_SUB",
            "vendor_field": "MSISDN",
            "canonical_table": "subscriber_profile",
            "canonical_field": "msisdn",
            "confidence": 0.90,
        })

        mappings = await mapping_repo.get_by_schema_id("s1")
        assert len(mappings) == 2
        # Should be ordered by confidence DESC
        assert mappings[0]["confidence"] >= mappings[1]["confidence"]

    @pytest.mark.asyncio
    async def test_list_all(self, mapping_repo: SQLiteMappingRepository):
        await mapping_repo.save({
            "vendor_table": "T1", "vendor_field": "F1",
            "canonical_table": "t1", "canonical_field": "f1",
        })
        all_mappings = await mapping_repo.list_all()
        assert len(all_mappings) == 1

    @pytest.mark.asyncio
    async def test_get_by_schema_empty(self, mapping_repo: SQLiteMappingRepository):
        result = await mapping_repo.get_by_schema_id("nonexistent")
        assert result == []


# ------------------------------------------------------------------
# ExportRepository tests
# ------------------------------------------------------------------

class TestExportRepository:
    @pytest.mark.asyncio
    async def test_save_and_get(self, export_repo: SQLiteExportRepository, user_repo: SQLiteUserRepository):
        # Create user first (foreign key)
        await user_repo.create({"id": "u1", "username": "exp_user1", "hashed_password": "h"})

        saved = await export_repo.save({
            "id": "e1",
            "user_id": "u1",
            "domains": ["subscriber", "cdr_event"],
            "jurisdiction": "SA",
            "file_count": 5,
            "total_size": 12345,
        })
        assert saved["id"] == "e1"

        fetched = await export_repo.get_by_id("e1")
        assert fetched is not None
        assert fetched["jurisdiction"] == "SA"
        assert fetched["file_count"] == 5

    @pytest.mark.asyncio
    async def test_list_by_user(self, export_repo: SQLiteExportRepository, user_repo: SQLiteUserRepository):
        await user_repo.create({"id": "u1", "username": "exp_u1", "hashed_password": "h"})
        await user_repo.create({"id": "u2", "username": "exp_u2", "hashed_password": "h"})

        await export_repo.save({"id": "e1", "user_id": "u1", "domains": []})
        await export_repo.save({"id": "e2", "user_id": "u1", "domains": []})
        await export_repo.save({"id": "e3", "user_id": "u2", "domains": []})

        u1_exports = await export_repo.list_by_user("u1")
        assert len(u1_exports) == 2

        u2_exports = await export_repo.list_by_user("u2")
        assert len(u2_exports) == 1

    @pytest.mark.asyncio
    async def test_save_without_user(self, export_repo: SQLiteExportRepository):
        """Exports with no user_id (NULL) should be fine."""
        saved = await export_repo.save({
            "id": "e_anon",
            "domains": ["subscriber"],
            "file_count": 2,
        })
        assert saved["id"] == "e_anon"
        fetched = await export_repo.get_by_id("e_anon")
        assert fetched is not None

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, export_repo: SQLiteExportRepository):
        assert await export_repo.get_by_id("nope") is None


# ------------------------------------------------------------------
# AuditRepository tests
# ------------------------------------------------------------------

class TestAuditRepository:
    @pytest.mark.asyncio
    async def test_log_and_query(self, audit_repo: SQLiteAuditRepository):
        entry = await audit_repo.log(
            user_id="u1",
            action="export",
            resource_type="pack",
            resource_id="e1",
            details="Generated full artefact pack",
        )
        assert entry["id"] is not None
        assert entry["action"] == "export"

        results = await audit_repo.query(user_id="u1")
        assert len(results) == 1
        assert results[0]["action"] == "export"

    @pytest.mark.asyncio
    async def test_query_by_action(self, audit_repo: SQLiteAuditRepository):
        await audit_repo.log("u1", "login", "auth")
        await audit_repo.log("u1", "export", "pack")
        await audit_repo.log("u2", "login", "auth")

        logins = await audit_repo.query(action="login")
        assert len(logins) == 2

        exports = await audit_repo.query(action="export")
        assert len(exports) == 1

    @pytest.mark.asyncio
    async def test_query_all(self, audit_repo: SQLiteAuditRepository):
        await audit_repo.log("u1", "a", "t")
        await audit_repo.log("u2", "b", "t")
        all_entries = await audit_repo.query()
        assert len(all_entries) == 2

    @pytest.mark.asyncio
    async def test_query_with_limit(self, audit_repo: SQLiteAuditRepository):
        for i in range(10):
            await audit_repo.log(f"u{i}", "action", "type")

        limited = await audit_repo.query(limit=3)
        assert len(limited) == 3

    @pytest.mark.asyncio
    async def test_query_since(self, audit_repo: SQLiteAuditRepository):
        await audit_repo.log("u1", "old", "t")
        # Query with a timestamp in the future should return nothing
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        results = await audit_repo.query(since=future)
        assert len(results) == 0

        # Query with a timestamp in the past should return everything
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        results = await audit_repo.query(since=past)
        assert len(results) == 1


# ------------------------------------------------------------------
# Integration: full workflow
# ------------------------------------------------------------------

class TestDatabaseIntegration:
    @pytest.mark.asyncio
    async def test_full_workflow(self, db: DatabaseManager):
        """Simulate a realistic user workflow end-to-end."""
        user_repo = SQLiteUserRepository(db)
        schema_repo = SQLiteSchemaRepository(db)
        mapping_repo = SQLiteMappingRepository(db)
        export_repo = SQLiteExportRepository(db)
        audit_repo = SQLiteAuditRepository(db)

        # 1. Create user
        user = await user_repo.create({
            "username": "workflow_user",
            "name": "Workflow Tester",
            "email": "wf@test.com",
            "role": "admin",
            "hashed_password": "hashed",
        })
        user_id = user["id"]

        # 2. Upload schema
        schema = await schema_repo.save({
            "user_id": user_id,
            "content": "CREATE TABLE subscriber (id INT, msisdn VARCHAR(20));",
            "format": "sql",
            "tables_found": 1,
            "columns_found": 2,
            "detected_vendor": "amdocs",
            "vendor_confidence": 0.92,
        })
        schema_id = schema["id"]

        # 3. Save mapping suggestions
        await mapping_repo.save({
            "schema_id": schema_id,
            "vendor_table": "subscriber",
            "vendor_field": "id",
            "canonical_table": "subscriber_profile",
            "canonical_field": "subscriber_id",
            "confidence": 0.95,
        })

        # 4. Export artefacts
        export = await export_repo.save({
            "user_id": user_id,
            "domains": ["subscriber"],
            "jurisdiction": "SA",
            "file_count": 10,
            "total_size": 50000,
        })

        # 5. Log the export action
        await audit_repo.log(
            user_id=user_id,
            action="export",
            resource_type="pack",
            resource_id=export["id"],
        )

        # Verify everything is queryable
        mappings = await mapping_repo.get_by_schema_id(schema_id)
        assert len(mappings) == 1

        exports = await export_repo.list_by_user(user_id)
        assert len(exports) == 1

        audit_entries = await audit_repo.query(user_id=user_id)
        assert len(audit_entries) == 1
        assert audit_entries[0]["resource_type"] == "pack"

    @pytest.mark.asyncio
    async def test_cascade_delete_schema_removes_mappings(self, db: DatabaseManager):
        """Deleting a schema should cascade-delete its mappings."""
        schema_repo = SQLiteSchemaRepository(db)
        mapping_repo = SQLiteMappingRepository(db)

        await schema_repo.save({"id": "cs1", "content": "x"})
        await mapping_repo.save({
            "schema_id": "cs1",
            "vendor_table": "T", "vendor_field": "F",
            "canonical_table": "t", "canonical_field": "f",
        })

        # Verify mapping exists
        assert len(await mapping_repo.get_by_schema_id("cs1")) == 1

        # Delete schema
        await schema_repo.delete("cs1")

        # Mappings should be gone (cascade)
        assert len(await mapping_repo.get_by_schema_id("cs1")) == 0


# ------------------------------------------------------------------
# Fallback / backward compatibility tests
# ------------------------------------------------------------------

class TestFallbackBehavior:
    @pytest.mark.asyncio
    async def test_unavailable_before_init(self):
        db = DatabaseManager(url=":memory:")
        assert not db.is_available

    @pytest.mark.asyncio
    async def test_get_connection_raises_before_init(self):
        db = DatabaseManager(url=":memory:")
        with pytest.raises(RuntimeError):
            db.get_connection()

    @pytest.mark.asyncio
    async def test_double_close_is_safe(self):
        db = DatabaseManager(url=":memory:")
        await db.initialize()
        await db.close()
        await db.close()  # should not raise
        assert not db.is_available
