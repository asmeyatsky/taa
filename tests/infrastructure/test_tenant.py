"""Tests for multi-tenant support: tenant resolution, data isolation,
organization CRUD, and schema migration from v1 to v2.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from taa.infrastructure.database.connection import DatabaseManager
from taa.infrastructure.database.models import SCHEMA_VERSION, TABLES
from taa.infrastructure.database.migrations import (
    apply_migrations,
    _get_current_version,
    _set_version,
    _migrate_v2,
    MIGRATIONS,
)
from taa.infrastructure.database.repositories import (
    SQLiteOrganizationRepository,
    SQLiteUserRepository,
    SQLiteSchemaRepository,
    SQLiteMappingRepository,
    SQLiteExportRepository,
    SQLiteAuditRepository,
)
from taa.presentation.api.tenant import (
    set_current_tenant,
    get_tenant_id,
    clear_tenant,
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
async def org_repo(db: DatabaseManager):
    return SQLiteOrganizationRepository(db)


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


async def _create_org(org_repo, org_id="org-1", name="Test Org", slug="test-org", plan="free"):
    """Helper to create an organization."""
    return await org_repo.create({
        "id": org_id,
        "name": name,
        "slug": slug,
        "plan": plan,
        "max_users": 10,
    })


# ------------------------------------------------------------------
# Organization CRUD tests
# ------------------------------------------------------------------

class TestOrganizationCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_by_id(self, org_repo):
        org = await _create_org(org_repo)
        assert org["id"] == "org-1"
        assert org["name"] == "Test Org"
        assert org["slug"] == "test-org"

        fetched = await org_repo.get_by_id("org-1")
        assert fetched is not None
        assert fetched["name"] == "Test Org"
        assert fetched["plan"] == "free"

    @pytest.mark.asyncio
    async def test_get_by_slug(self, org_repo):
        await _create_org(org_repo)
        fetched = await org_repo.get_by_slug("test-org")
        assert fetched is not None
        assert fetched["id"] == "org-1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, org_repo):
        assert await org_repo.get_by_id("nope") is None
        assert await org_repo.get_by_slug("nope") is None

    @pytest.mark.asyncio
    async def test_list_all(self, org_repo):
        await _create_org(org_repo, "org-1", "Alpha", "alpha")
        await _create_org(org_repo, "org-2", "Beta", "beta")
        orgs = await org_repo.list_all()
        assert len(orgs) == 2
        names = {o["name"] for o in orgs}
        assert names == {"Alpha", "Beta"}

    @pytest.mark.asyncio
    async def test_update(self, org_repo):
        await _create_org(org_repo)
        updated = await org_repo.update("org-1", {"name": "Updated Org", "plan": "pro"})
        assert updated is not None
        assert updated["name"] == "Updated Org"
        assert updated["plan"] == "pro"

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, org_repo):
        result = await org_repo.update("nope", {"name": "X"})
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, org_repo):
        await _create_org(org_repo)
        assert await org_repo.delete("org-1") is True
        assert await org_repo.get_by_id("org-1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, org_repo):
        assert await org_repo.delete("nope") is False

    @pytest.mark.asyncio
    async def test_unique_slug_constraint(self, org_repo):
        await _create_org(org_repo, "org-1", "First", "unique-slug")
        with pytest.raises(Exception):
            await _create_org(org_repo, "org-2", "Second", "unique-slug")

    @pytest.mark.asyncio
    async def test_update_is_active(self, org_repo):
        await _create_org(org_repo)
        updated = await org_repo.update("org-1", {"is_active": False})
        assert updated is not None
        assert updated["is_active"] == 0  # SQLite stores as int

    @pytest.mark.asyncio
    async def test_auto_generates_id(self, org_repo):
        org = await org_repo.create({"name": "Auto ID", "slug": "auto-id"})
        assert org["id"] is not None
        assert len(org["id"]) > 0


# ------------------------------------------------------------------
# Tenant context tests
# ------------------------------------------------------------------

class TestTenantContext:
    def test_set_and_get_tenant(self):
        set_current_tenant("org-abc")
        assert get_tenant_id() == "org-abc"
        clear_tenant()
        assert get_tenant_id() is None

    def test_default_tenant_is_none(self):
        clear_tenant()
        assert get_tenant_id() is None

    def test_clear_tenant(self):
        set_current_tenant("org-xyz")
        clear_tenant()
        assert get_tenant_id() is None

    def test_overwrite_tenant(self):
        set_current_tenant("org-1")
        set_current_tenant("org-2")
        assert get_tenant_id() == "org-2"
        clear_tenant()


# ------------------------------------------------------------------
# Data isolation tests
# ------------------------------------------------------------------

class TestDataIsolation:
    @pytest.mark.asyncio
    async def test_users_filtered_by_org(self, org_repo, user_repo):
        await _create_org(org_repo, "org-a", "Org A", "org-a")
        await _create_org(org_repo, "org-b", "Org B", "org-b")

        await user_repo.create({
            "id": "u1", "username": "alice", "hashed_password": "h",
            "org_id": "org-a",
        })
        await user_repo.create({
            "id": "u2", "username": "bob", "hashed_password": "h",
            "org_id": "org-b",
        })
        await user_repo.create({
            "id": "u3", "username": "charlie", "hashed_password": "h",
            "org_id": "org-a",
        })

        # Filter by org-a
        org_a_users = await user_repo.list_all(org_id="org-a")
        assert len(org_a_users) == 2
        usernames_a = {u["username"] for u in org_a_users}
        assert usernames_a == {"alice", "charlie"}

        # Filter by org-b
        org_b_users = await user_repo.list_all(org_id="org-b")
        assert len(org_b_users) == 1
        assert org_b_users[0]["username"] == "bob"

        # No filter returns all
        all_users = await user_repo.list_all()
        assert len(all_users) == 3

    @pytest.mark.asyncio
    async def test_schemas_filtered_by_org(self, org_repo, schema_repo):
        await _create_org(org_repo, "org-a", "Org A", "org-a")
        await _create_org(org_repo, "org-b", "Org B", "org-b")

        await schema_repo.save({"id": "s1", "content": "a", "org_id": "org-a"})
        await schema_repo.save({"id": "s2", "content": "b", "org_id": "org-b"})
        await schema_repo.save({"id": "s3", "content": "c", "org_id": "org-a"})

        org_a = await schema_repo.list_all(org_id="org-a")
        assert len(org_a) == 2

        org_b = await schema_repo.list_all(org_id="org-b")
        assert len(org_b) == 1

        all_schemas = await schema_repo.list_all()
        assert len(all_schemas) == 3

    @pytest.mark.asyncio
    async def test_mappings_filtered_by_org(self, org_repo, mapping_repo):
        await _create_org(org_repo, "org-a", "Org A", "org-a")
        await _create_org(org_repo, "org-b", "Org B", "org-b")

        await mapping_repo.save({
            "vendor_table": "T1", "vendor_field": "F1",
            "canonical_table": "t1", "canonical_field": "f1",
            "org_id": "org-a",
        })
        await mapping_repo.save({
            "vendor_table": "T2", "vendor_field": "F2",
            "canonical_table": "t2", "canonical_field": "f2",
            "org_id": "org-b",
        })

        org_a = await mapping_repo.list_all(org_id="org-a")
        assert len(org_a) == 1

        org_b = await mapping_repo.list_all(org_id="org-b")
        assert len(org_b) == 1

    @pytest.mark.asyncio
    async def test_audit_log_filtered_by_org(self, org_repo, audit_repo):
        await _create_org(org_repo, "org-a", "Org A", "org-a")
        await _create_org(org_repo, "org-b", "Org B", "org-b")

        await audit_repo.log("u1", "action-a", "type", org_id="org-a")
        await audit_repo.log("u2", "action-b", "type", org_id="org-b")
        await audit_repo.log("u3", "action-c", "type", org_id="org-a")

        org_a = await audit_repo.query(org_id="org-a")
        assert len(org_a) == 2

        org_b = await audit_repo.query(org_id="org-b")
        assert len(org_b) == 1

        all_entries = await audit_repo.query()
        assert len(all_entries) == 3

    @pytest.mark.asyncio
    async def test_user_org_id_persisted(self, org_repo, user_repo):
        await _create_org(org_repo, "org-1", "My Org", "my-org")

        await user_repo.create({
            "id": "u1", "username": "tenant_user", "hashed_password": "h",
            "org_id": "org-1",
        })

        fetched = await user_repo.get_by_id("u1")
        assert fetched is not None
        assert fetched["org_id"] == "org-1"

    @pytest.mark.asyncio
    async def test_user_without_org(self, user_repo):
        """Users without an org_id should still work."""
        await user_repo.create({
            "id": "u-no-org", "username": "noorg", "hashed_password": "h",
        })
        fetched = await user_repo.get_by_id("u-no-org")
        assert fetched is not None
        assert fetched["org_id"] is None

    @pytest.mark.asyncio
    async def test_export_with_org_id(self, org_repo, user_repo, export_repo):
        await _create_org(org_repo, "org-1", "Org 1", "org-1")
        await user_repo.create({
            "id": "u1", "username": "exp_user", "hashed_password": "h",
            "org_id": "org-1",
        })

        saved = await export_repo.save({
            "id": "e1", "user_id": "u1", "org_id": "org-1",
            "domains": [], "file_count": 1,
        })
        assert saved["org_id"] == "org-1"

        fetched = await export_repo.get_by_id("e1")
        assert fetched is not None
        assert fetched["org_id"] == "org-1"

    @pytest.mark.asyncio
    async def test_update_user_org_id(self, org_repo, user_repo):
        """Test that a user's org_id can be changed."""
        await _create_org(org_repo, "org-a", "Org A", "org-a")
        await _create_org(org_repo, "org-b", "Org B", "org-b")

        await user_repo.create({
            "id": "u1", "username": "movable", "hashed_password": "h",
            "org_id": "org-a",
        })

        updated = await user_repo.update("u1", {"org_id": "org-b"})
        assert updated is not None
        assert updated["org_id"] == "org-b"


# ------------------------------------------------------------------
# Migration tests (v1 -> v2)
# ------------------------------------------------------------------

class TestMigrationV1ToV2:
    @pytest.mark.asyncio
    async def test_fresh_db_has_v2_schema(self, db):
        """A fresh database should be created at schema version 2."""
        conn = db.get_connection()
        version = await _get_current_version(conn)
        assert version == 2

        # Verify organizations table exists
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='organizations'"
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_organizations_table_has_correct_columns(self, db):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA table_info(organizations)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}
        expected = {"id", "name", "slug", "plan", "max_users", "is_active", "created_at"}
        assert expected == col_names

    @pytest.mark.asyncio
    async def test_users_table_has_org_id(self, db):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA table_info(users)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}
        assert "org_id" in col_names

    @pytest.mark.asyncio
    async def test_schemas_table_has_org_id(self, db):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA table_info(schemas)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}
        assert "org_id" in col_names

    @pytest.mark.asyncio
    async def test_mappings_table_has_org_id(self, db):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA table_info(mappings)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}
        assert "org_id" in col_names

    @pytest.mark.asyncio
    async def test_exports_table_has_org_id(self, db):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA table_info(exports)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}
        assert "org_id" in col_names

    @pytest.mark.asyncio
    async def test_audit_log_has_org_id(self, db):
        conn = db.get_connection()
        cursor = await conn.execute("PRAGMA table_info(audit_log)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}
        assert "org_id" in col_names

    @pytest.mark.asyncio
    async def test_migrate_v2_is_idempotent(self, db):
        """Running _migrate_v2 twice should not fail."""
        conn = db.get_connection()
        # The migration has already run during init, run it again
        await _migrate_v2(conn)
        await conn.commit()
        # Should still work
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='organizations'"
        )
        row = await cursor.fetchone()
        assert row is not None

    @pytest.mark.asyncio
    async def test_migration_from_v1_schema(self):
        """Simulate upgrading from a v1 database (no org tables)."""
        import aiosqlite
        from taa.infrastructure.database import models as m

        # Create a minimal v1 database manually
        conn = await aiosqlite.connect(":memory:")
        conn.row_factory = aiosqlite.Row

        # Create v1 tables (without org_id columns, without organizations table)
        await conn.execute("""
            CREATE TABLE schema_version (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL DEFAULT 1,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.execute("INSERT INTO schema_version (id, version) VALUES (1, 1)")

        await conn.execute("""
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                email TEXT NOT NULL DEFAULT '',
                role TEXT NOT NULL DEFAULT 'user',
                hashed_password TEXT NOT NULL,
                disabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.execute("""
            CREATE TABLE schemas (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                content TEXT NOT NULL,
                format TEXT NOT NULL DEFAULT 'auto',
                tables_found INTEGER NOT NULL DEFAULT 0,
                columns_found INTEGER NOT NULL DEFAULT 0,
                detected_vendor TEXT,
                vendor_confidence REAL NOT NULL DEFAULT 0.0,
                uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.execute("""
            CREATE TABLE mappings (
                id TEXT PRIMARY KEY,
                schema_id TEXT,
                vendor_table TEXT NOT NULL,
                vendor_field TEXT NOT NULL,
                canonical_table TEXT NOT NULL,
                canonical_field TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.0,
                match_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.execute("""
            CREATE TABLE exports (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                domains TEXT NOT NULL DEFAULT '[]',
                jurisdiction TEXT NOT NULL DEFAULT 'SA',
                file_count INTEGER NOT NULL DEFAULT 0,
                total_size INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'completed',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                action TEXT NOT NULL,
                resource_type TEXT NOT NULL DEFAULT '',
                resource_id TEXT,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await conn.commit()

        # Insert some v1 data
        await conn.execute(
            "INSERT INTO users (id, username, hashed_password) VALUES (?, ?, ?)",
            ("u1", "olduser", "hash123"),
        )
        await conn.commit()

        # Verify starting at v1
        version = await _get_current_version(conn)
        assert version == 1

        # Apply migration
        await _migrate_v2(conn)
        await conn.commit()
        await _set_version(conn, 2)

        # Verify version is now 2
        version = await _get_current_version(conn)
        assert version == 2

        # Verify organizations table exists
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='organizations'"
        )
        assert (await cursor.fetchone()) is not None

        # Verify org_id column exists on users
        cursor = await conn.execute("PRAGMA table_info(users)")
        rows = await cursor.fetchall()
        col_names = {row[1] for row in rows}
        assert "org_id" in col_names

        # Verify old data still accessible
        cursor = await conn.execute("SELECT * FROM users WHERE id = ?", ("u1",))
        row = await cursor.fetchone()
        assert row is not None
        row_dict = dict(row)
        assert row_dict["username"] == "olduser"
        assert row_dict["org_id"] is None  # Old users have NULL org_id

        # Verify we can insert with org_id
        await conn.execute(
            "INSERT INTO organizations (id, name, slug) VALUES (?, ?, ?)",
            ("org-new", "New Org", "new-org"),
        )
        await conn.execute(
            "UPDATE users SET org_id = ? WHERE id = ?",
            ("org-new", "u1"),
        )
        await conn.commit()

        cursor = await conn.execute("SELECT org_id FROM users WHERE id = ?", ("u1",))
        row = await cursor.fetchone()
        assert row[0] == "org-new"

        await conn.close()


# ------------------------------------------------------------------
# Tenant middleware integration (unit-level)
# ------------------------------------------------------------------

class TestTenantResolution:
    def _make_app(self, secret: str = "test-secret") -> "FastAPI":
        """Create a minimal FastAPI app with tenant middleware for testing."""
        import fastapi
        from taa.presentation.api.middleware.tenant import TenantMiddleware
        from taa.presentation.api.tenant import get_tenant_id

        app = fastapi.FastAPI()
        app.add_middleware(TenantMiddleware, secret_key=secret, algorithm="HS256")

        @app.get("/test")
        def test_endpoint():
            # Read from contextvars instead of request.state
            return {"tenant_id": get_tenant_id()}

        @app.get("/api/health")
        def health():
            return {"status": "ok"}

        @app.get("/api/auth/token")
        def auth_token():
            return {"token": "test"}

        return app

    def test_header_tenant_resolution(self):
        """X-Tenant-ID header should set tenant context."""
        from starlette.testclient import TestClient

        app = self._make_app()
        client = TestClient(app)

        response = client.get("/test", headers={"X-Tenant-ID": "org-123"})
        assert response.status_code == 200, f"Response body: {response.text}"
        assert response.json()["tenant_id"] == "org-123"

    def test_no_tenant_header(self):
        """Without X-Tenant-ID header, tenant should be None."""
        from starlette.testclient import TestClient

        app = self._make_app()
        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["tenant_id"] is None

    def test_jwt_tenant_resolution(self):
        """JWT token with org_id claim should set tenant context."""
        from starlette.testclient import TestClient
        from jose import jwt

        secret = "test-secret-key"
        app = self._make_app(secret=secret)
        client = TestClient(app)

        token = jwt.encode(
            {"sub": "testuser", "org_id": "org-jwt-123"},
            secret,
            algorithm="HS256",
        )
        response = client.get(
            "/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "org-jwt-123"

    def test_tenant_mismatch_returns_403(self):
        """Mismatched X-Tenant-ID header and JWT org_id should return 403."""
        from starlette.testclient import TestClient
        from jose import jwt

        secret = "test-secret-key"
        app = self._make_app(secret=secret)
        client = TestClient(app)

        token = jwt.encode(
            {"sub": "testuser", "org_id": "org-jwt"},
            secret,
            algorithm="HS256",
        )
        response = client.get(
            "/test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": "org-different",
            },
        )
        assert response.status_code == 403
        assert "mismatch" in response.json()["detail"].lower()

    def test_matching_header_and_jwt(self):
        """Matching X-Tenant-ID and JWT org_id should work fine."""
        from starlette.testclient import TestClient
        from jose import jwt

        secret = "test-secret-key"
        app = self._make_app(secret=secret)
        client = TestClient(app)

        token = jwt.encode(
            {"sub": "testuser", "org_id": "org-match"},
            secret,
            algorithm="HS256",
        )
        response = client.get(
            "/test",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": "org-match",
            },
        )
        assert response.status_code == 200
        assert response.json()["tenant_id"] == "org-match"

    def test_exempt_paths_skip_tenant(self):
        """Health and auth endpoints should skip tenant resolution."""
        from starlette.testclient import TestClient

        app = self._make_app()
        client = TestClient(app)

        # These should work without tenant headers
        response = client.get("/api/health")
        assert response.status_code == 200

        response = client.get("/api/auth/token")
        assert response.status_code == 200


# ------------------------------------------------------------------
# Full multi-tenant workflow integration
# ------------------------------------------------------------------

class TestMultiTenantWorkflow:
    @pytest.mark.asyncio
    async def test_full_isolation_workflow(self, db):
        """End-to-end test: two organizations with isolated data."""
        org_repo = SQLiteOrganizationRepository(db)
        user_repo = SQLiteUserRepository(db)
        schema_repo = SQLiteSchemaRepository(db)
        mapping_repo = SQLiteMappingRepository(db)
        audit_repo = SQLiteAuditRepository(db)

        # Create two orgs
        org_a = await org_repo.create({
            "id": "org-alpha", "name": "Alpha Corp",
            "slug": "alpha", "plan": "pro", "max_users": 50,
        })
        org_b = await org_repo.create({
            "id": "org-beta", "name": "Beta Inc",
            "slug": "beta", "plan": "enterprise", "max_users": 100,
        })

        # Create users in each org
        user_a = await user_repo.create({
            "id": "ua1", "username": "alpha_user",
            "hashed_password": "h", "org_id": "org-alpha",
        })
        user_b = await user_repo.create({
            "id": "ub1", "username": "beta_user",
            "hashed_password": "h", "org_id": "org-beta",
        })

        # Upload schemas in each org
        await schema_repo.save({
            "id": "sa1", "content": "alpha schema", "org_id": "org-alpha",
            "user_id": "ua1",
        })
        await schema_repo.save({
            "id": "sb1", "content": "beta schema", "org_id": "org-beta",
            "user_id": "ub1",
        })
        await schema_repo.save({
            "id": "sa2", "content": "alpha schema 2", "org_id": "org-alpha",
            "user_id": "ua1",
        })

        # Save mappings
        await mapping_repo.save({
            "vendor_table": "T", "vendor_field": "F",
            "canonical_table": "t", "canonical_field": "f",
            "org_id": "org-alpha",
        })
        await mapping_repo.save({
            "vendor_table": "T2", "vendor_field": "F2",
            "canonical_table": "t2", "canonical_field": "f2",
            "org_id": "org-beta",
        })

        # Log audit events
        await audit_repo.log("ua1", "upload", "schema", org_id="org-alpha")
        await audit_repo.log("ub1", "upload", "schema", org_id="org-beta")

        # Verify isolation
        alpha_users = await user_repo.list_all(org_id="org-alpha")
        assert len(alpha_users) == 1
        assert alpha_users[0]["username"] == "alpha_user"

        beta_users = await user_repo.list_all(org_id="org-beta")
        assert len(beta_users) == 1
        assert beta_users[0]["username"] == "beta_user"

        alpha_schemas = await schema_repo.list_all(org_id="org-alpha")
        assert len(alpha_schemas) == 2

        beta_schemas = await schema_repo.list_all(org_id="org-beta")
        assert len(beta_schemas) == 1

        alpha_mappings = await mapping_repo.list_all(org_id="org-alpha")
        assert len(alpha_mappings) == 1

        alpha_audit = await audit_repo.query(org_id="org-alpha")
        assert len(alpha_audit) == 1
        assert alpha_audit[0]["user_id"] == "ua1"

        beta_audit = await audit_repo.query(org_id="org-beta")
        assert len(beta_audit) == 1
        assert beta_audit[0]["user_id"] == "ub1"

        # Global queries still return everything
        all_users = await user_repo.list_all()
        assert len(all_users) == 2

        all_schemas = await schema_repo.list_all()
        assert len(all_schemas) == 3
