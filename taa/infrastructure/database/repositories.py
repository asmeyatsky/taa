"""SQLite repository implementations for each entity.

Every repository takes a ``DatabaseManager`` and uses its connection
for async reads/writes.  All repositories implement the abstract
interfaces defined in ``taa.domain.repositories``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import aiosqlite

from taa.domain.repositories import (
    OrganizationRepository,
    UserRepository,
    SchemaRepository,
    MappingRepository,
    ExportRepository,
    AuditRepository,
)
from taa.infrastructure.database.connection import DatabaseManager


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    """Convert an ``aiosqlite.Row`` to a plain dict."""
    return dict(row)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ======================================================================
# OrganizationRepository
# ======================================================================

class SQLiteOrganizationRepository(OrganizationRepository):
    """SQLite-backed organization (tenant) storage."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def _conn(self) -> aiosqlite.Connection:
        return self._db.get_connection()

    async def get_by_id(self, org_id: str) -> dict[str, Any] | None:
        cursor = await self._conn().execute(
            "SELECT * FROM organizations WHERE id = ?", (org_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        cursor = await self._conn().execute(
            "SELECT * FROM organizations WHERE slug = ?", (slug,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def list_all(self) -> list[dict[str, Any]]:
        cursor = await self._conn().execute(
            "SELECT * FROM organizations ORDER BY created_at"
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def create(self, org: dict[str, Any]) -> dict[str, Any]:
        org_id = org.get("id", str(uuid.uuid4()))
        now = _utcnow()
        await self._conn().execute(
            """INSERT INTO organizations (id, name, slug, plan, max_users, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                org_id,
                org["name"],
                org["slug"],
                org.get("plan", "free"),
                org.get("max_users", 5),
                int(org.get("is_active", True)),
                now,
            ),
        )
        await self._conn().commit()
        return {**org, "id": org_id, "created_at": now}

    async def update(self, org_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self.get_by_id(org_id)
        if existing is None:
            return None

        allowed = {"name", "slug", "plan", "max_users", "is_active"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return existing

        if "is_active" in updates:
            updates["is_active"] = int(updates["is_active"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [org_id]
        await self._conn().execute(
            f"UPDATE organizations SET {set_clause} WHERE id = ?",
            values,
        )
        await self._conn().commit()
        return await self.get_by_id(org_id)

    async def delete(self, org_id: str) -> bool:
        cursor = await self._conn().execute(
            "DELETE FROM organizations WHERE id = ?", (org_id,)
        )
        await self._conn().commit()
        return cursor.rowcount > 0


# ======================================================================
# UserRepository
# ======================================================================

class SQLiteUserRepository(UserRepository):
    """SQLite-backed user storage."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def _conn(self) -> aiosqlite.Connection:
        return self._db.get_connection()

    async def get_by_username(self, username: str) -> dict[str, Any] | None:
        cursor = await self._conn().execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        cursor = await self._conn().execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def create(self, user: dict[str, Any]) -> dict[str, Any]:
        user_id = user.get("id", str(uuid.uuid4()))
        now = _utcnow()
        await self._conn().execute(
            """INSERT INTO users (id, username, name, email, role, hashed_password, disabled, org_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                user["username"],
                user.get("name", ""),
                user.get("email", ""),
                user.get("role", "user"),
                user["hashed_password"],
                int(user.get("disabled", False)),
                user.get("org_id"),
                now,
                now,
            ),
        )
        await self._conn().commit()
        return {**user, "id": user_id, "created_at": now, "updated_at": now}

    async def update(self, user_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
        existing = await self.get_by_id(user_id)
        if existing is None:
            return None

        allowed = {"username", "name", "email", "role", "hashed_password", "disabled", "org_id"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return existing

        # Handle boolean -> int for disabled
        if "disabled" in updates:
            updates["disabled"] = int(updates["disabled"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [_utcnow(), user_id]
        await self._conn().execute(
            f"UPDATE users SET {set_clause}, updated_at = ? WHERE id = ?",
            values,
        )
        await self._conn().commit()
        return await self.get_by_id(user_id)

    async def list_all(self, *, org_id: str | None = None) -> list[dict[str, Any]]:
        if org_id is not None:
            cursor = await self._conn().execute(
                "SELECT * FROM users WHERE org_id = ? ORDER BY created_at",
                (org_id,),
            )
        else:
            cursor = await self._conn().execute("SELECT * FROM users ORDER BY created_at")
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def delete(self, user_id: str) -> bool:
        cursor = await self._conn().execute(
            "DELETE FROM users WHERE id = ?", (user_id,)
        )
        await self._conn().commit()
        return cursor.rowcount > 0


# ======================================================================
# SchemaRepository
# ======================================================================

class SQLiteSchemaRepository(SchemaRepository):
    """SQLite-backed schema upload storage."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def _conn(self) -> aiosqlite.Connection:
        return self._db.get_connection()

    async def save(self, schema: dict[str, Any]) -> dict[str, Any]:
        schema_id = schema.get("id", str(uuid.uuid4()))
        now = _utcnow()
        await self._conn().execute(
            """INSERT INTO schemas
               (id, user_id, org_id, content, format, tables_found, columns_found,
                detected_vendor, vendor_confidence, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                schema_id,
                schema.get("user_id"),
                schema.get("org_id"),
                schema.get("content", ""),
                schema.get("format", "auto"),
                schema.get("tables_found", 0),
                schema.get("columns_found", 0),
                schema.get("detected_vendor"),
                schema.get("vendor_confidence", 0.0),
                now,
            ),
        )
        await self._conn().commit()
        return {**schema, "id": schema_id, "uploaded_at": now}

    async def get_by_id(self, schema_id: str) -> dict[str, Any] | None:
        cursor = await self._conn().execute(
            "SELECT * FROM schemas WHERE id = ?", (schema_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def list_all(self, limit: int = 100, *, org_id: str | None = None) -> list[dict[str, Any]]:
        if org_id is not None:
            cursor = await self._conn().execute(
                "SELECT * FROM schemas WHERE org_id = ? ORDER BY uploaded_at DESC LIMIT ?",
                (org_id, limit),
            )
        else:
            cursor = await self._conn().execute(
                "SELECT * FROM schemas ORDER BY uploaded_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def delete(self, schema_id: str) -> bool:
        cursor = await self._conn().execute(
            "DELETE FROM schemas WHERE id = ?", (schema_id,)
        )
        await self._conn().commit()
        return cursor.rowcount > 0


# ======================================================================
# MappingRepository
# ======================================================================

class SQLiteMappingRepository(MappingRepository):
    """SQLite-backed mapping result storage."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def _conn(self) -> aiosqlite.Connection:
        return self._db.get_connection()

    async def save(self, mapping: dict[str, Any]) -> dict[str, Any]:
        mapping_id = mapping.get("id", str(uuid.uuid4()))
        now = _utcnow()
        await self._conn().execute(
            """INSERT INTO mappings
               (id, schema_id, org_id, vendor_table, vendor_field, canonical_table,
                canonical_field, confidence, match_reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mapping_id,
                mapping.get("schema_id"),
                mapping.get("org_id"),
                mapping["vendor_table"],
                mapping["vendor_field"],
                mapping["canonical_table"],
                mapping["canonical_field"],
                mapping.get("confidence", 0.0),
                mapping.get("match_reason", ""),
                now,
            ),
        )
        await self._conn().commit()
        return {**mapping, "id": mapping_id, "created_at": now}

    async def get_by_schema_id(self, schema_id: str) -> list[dict[str, Any]]:
        cursor = await self._conn().execute(
            "SELECT * FROM mappings WHERE schema_id = ? ORDER BY confidence DESC",
            (schema_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def list_all(self, limit: int = 100, *, org_id: str | None = None) -> list[dict[str, Any]]:
        if org_id is not None:
            cursor = await self._conn().execute(
                "SELECT * FROM mappings WHERE org_id = ? ORDER BY created_at DESC LIMIT ?",
                (org_id, limit),
            )
        else:
            cursor = await self._conn().execute(
                "SELECT * FROM mappings ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


# ======================================================================
# ExportRepository
# ======================================================================

class SQLiteExportRepository(ExportRepository):
    """SQLite-backed export record storage."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def _conn(self) -> aiosqlite.Connection:
        return self._db.get_connection()

    async def save(self, export: dict[str, Any]) -> dict[str, Any]:
        export_id = export.get("id", str(uuid.uuid4()))
        now = _utcnow()
        domains = export.get("domains", [])
        if isinstance(domains, list):
            domains = json.dumps(domains)
        await self._conn().execute(
            """INSERT INTO exports
               (id, user_id, org_id, domains, jurisdiction, file_count, total_size,
                status, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                export_id,
                export.get("user_id"),
                export.get("org_id"),
                domains,
                export.get("jurisdiction", "SA"),
                export.get("file_count", 0),
                export.get("total_size", 0),
                export.get("status", "completed"),
                now,
                export.get("expires_at"),
            ),
        )
        await self._conn().commit()
        return {**export, "id": export_id, "created_at": now}

    async def get_by_id(self, export_id: str) -> dict[str, Any] | None:
        cursor = await self._conn().execute(
            "SELECT * FROM exports WHERE id = ?", (export_id,)
        )
        row = await cursor.fetchone()
        return _row_to_dict(row) if row else None

    async def list_by_user(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        cursor = await self._conn().execute(
            "SELECT * FROM exports WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]


# ======================================================================
# AuditRepository
# ======================================================================

class SQLiteAuditRepository(AuditRepository):
    """SQLite-backed audit log."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def _conn(self) -> aiosqlite.Connection:
        return self._db.get_connection()

    async def log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: str | None = None,
        username: str = "",
        ip_address: str | None = None,
        *,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        now = _utcnow()
        cursor = await self._conn().execute(
            """INSERT INTO audit_log
               (user_id, username, org_id, action, resource_type, resource_id, details, ip_address, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, org_id, action, resource_type, resource_id, details, ip_address, now),
        )
        await self._conn().commit()
        return {
            "id": cursor.lastrowid,
            "user_id": user_id,
            "username": username,
            "org_id": org_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
            "created_at": now,
        }

    async def query(
        self,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        *,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if action is not None:
            clauses.append("action = ?")
            params.append(action)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(since.strftime("%Y-%m-%d %H:%M:%S"))
        if org_id is not None:
            clauses.append("org_id = ?")
            params.append(org_id)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.extend([limit, offset])

        cursor = await self._conn().execute(
            f"SELECT * FROM audit_log{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def count(
        self,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
    ) -> int:
        clauses: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            params.append(user_id)
        if action is not None:
            clauses.append("action = ?")
            params.append(action)
        if since is not None:
            clauses.append("created_at >= ?")
            params.append(since.strftime("%Y-%m-%d %H:%M:%S"))

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        cursor = await self._conn().execute(
            f"SELECT COUNT(*) FROM audit_log{where}",
            params,
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
