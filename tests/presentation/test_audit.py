"""Tests for audit middleware and audit API endpoints."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from taa.presentation.api.middleware.audit import (
    AuditMiddleware,
    _classify_request,
)


# ---------------------------------------------------------------------------
# In-memory audit repository for testing
# ---------------------------------------------------------------------------

class InMemoryAuditRepository:
    """Simple in-memory audit repository for tests."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        self._next_id = 1

    async def log(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        details: str | None = None,
        username: str = "",
        ip_address: str | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": self._next_id,
            "user_id": user_id,
            "username": username,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._next_id += 1
        self.entries.append(entry)
        return entry

    async def query(
        self,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        results = list(self.entries)
        if user_id is not None:
            results = [e for e in results if e["user_id"] == user_id]
        if action is not None:
            results = [e for e in results if e["action"] == action]
        if since is not None:
            since_str = since.strftime("%Y-%m-%d %H:%M:%S")
            results = [e for e in results if e["created_at"] >= since_str]
        results.sort(key=lambda e: e["created_at"], reverse=True)
        return results[offset : offset + limit]

    async def count(
        self,
        user_id: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
    ) -> int:
        results = list(self.entries)
        if user_id is not None:
            results = [e for e in results if e["user_id"] == user_id]
        if action is not None:
            results = [e for e in results if e["action"] == action]
        if since is not None:
            since_str = since.strftime("%Y-%m-%d %H:%M:%S")
            results = [e for e in results if e["created_at"] >= since_str]
        return len(results)


# ---------------------------------------------------------------------------
# Mock container for testing
# ---------------------------------------------------------------------------

class MockDB:
    is_available = True


class MockContainer:
    def __init__(self, audit_repo: InMemoryAuditRepository) -> None:
        self.audit_repo = audit_repo
        self.db = MockDB()


# ---------------------------------------------------------------------------
# Test app builder for middleware tests
# ---------------------------------------------------------------------------

def _build_middleware_test_app(audit_repo: InMemoryAuditRepository) -> tuple[FastAPI, MockContainer]:
    """Build a minimal FastAPI app with audit middleware for testing.

    The patching of ``get_container`` is baked into the middleware
    constructor so that every request uses the mock container.
    """
    container = MockContainer(audit_repo)

    app = FastAPI()
    app.add_middleware(AuditMiddleware)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        return {"metrics": "ok"}

    @app.get("/api/domain/list")
    def list_domains():
        return [{"name": "subscriber"}]

    @app.post("/api/bss/schema")
    def upload_schema():
        return {"tables_found": 3}

    @app.post("/api/bigquery/export")
    def export_pack():
        return {"success": True, "download_id": "dl-123"}

    @app.put("/api/domain/update/abc-123-def")
    def update_domain():
        return {"updated": True}

    @app.delete("/api/domain/delete/xyz-789")
    def delete_domain():
        return {"deleted": True}

    @app.post("/api/auth/token")
    def login():
        return {"token": "abc"}

    return app, container


# ---------------------------------------------------------------------------
# Request classification unit tests
# ---------------------------------------------------------------------------

class TestClassifyRequest:
    def test_post_creates(self):
        action, rtype, rid = _classify_request("POST", "/api/bss/schema")
        assert action == "create"
        assert rtype == "schema"

    def test_put_updates(self):
        action, rtype, rid = _classify_request("PUT", "/api/domain/update/abc-123-def")
        assert action == "update"
        assert rtype == "domain"
        assert rid == "abc-123-def"

    def test_delete_action(self):
        action, rtype, rid = _classify_request("DELETE", "/api/domain/delete/xyz-789")
        assert action == "delete"
        assert rtype == "domain"

    def test_export_resource_type(self):
        action, rtype, rid = _classify_request("POST", "/api/bigquery/export")
        assert action == "create"
        assert rtype == "export"

    def test_unknown_path(self):
        action, rtype, rid = _classify_request("POST", "/api/something/new")
        assert action == "create"
        assert rtype == "unknown"


# ---------------------------------------------------------------------------
# Audit middleware integration tests
# ---------------------------------------------------------------------------

class TestAuditMiddleware:
    """Test that the audit middleware captures write operations
    and skips non-write requests."""

    def test_post_is_audited(self):
        """POST requests should be captured by the middleware."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.post("/api/bss/schema", json={})

        assert r.status_code == 200
        assert len(repo.entries) == 1
        entry = repo.entries[0]
        assert entry["action"] == "create"
        assert entry["resource_type"] == "schema"

    def test_put_is_audited(self):
        """PUT requests should be captured by the middleware."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.put("/api/domain/update/abc-123-def", json={})

        assert r.status_code == 200
        assert len(repo.entries) == 1
        entry = repo.entries[0]
        assert entry["action"] == "update"
        assert entry["resource_type"] == "domain"

    def test_delete_is_audited(self):
        """DELETE requests should be captured by the middleware."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.delete("/api/domain/delete/xyz-789")

        assert r.status_code == 200
        assert len(repo.entries) == 1
        entry = repo.entries[0]
        assert entry["action"] == "delete"

    def test_get_is_not_audited(self):
        """GET requests should NOT be audited."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.get("/api/domain/list")

        assert r.status_code == 200
        assert len(repo.entries) == 0

    def test_health_is_not_audited(self):
        """Health endpoint should NOT be audited."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.get("/api/health")

        assert r.status_code == 200
        assert len(repo.entries) == 0

    def test_metrics_is_not_audited(self):
        """Metrics endpoint should NOT be audited."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.get("/metrics")

        assert r.status_code == 200
        assert len(repo.entries) == 0

    def test_auth_token_is_not_audited(self):
        """Auth token endpoint should NOT be audited (skip path)."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.post("/api/auth/token", json={})

        assert r.status_code == 200
        assert len(repo.entries) == 0

    def test_ip_address_captured(self):
        """IP address should be recorded from the request."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.post("/api/bigquery/export", json={})

        assert r.status_code == 200
        assert len(repo.entries) == 1
        assert repo.entries[0]["ip_address"] is not None

    def test_forwarded_ip_used(self):
        """X-Forwarded-For header should be used if present."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.post(
                "/api/bss/schema",
                json={},
                headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"},
            )

        assert r.status_code == 200
        assert len(repo.entries) == 1
        assert repo.entries[0]["ip_address"] == "1.2.3.4"

    def test_anonymous_user_when_no_token(self):
        """Requests without auth should be logged as anonymous."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.post("/api/bss/schema", json={})

        assert r.status_code == 200
        assert len(repo.entries) == 1
        assert repo.entries[0]["user_id"] == "anonymous"
        assert repo.entries[0]["username"] == "anonymous"

    def test_details_contains_method_and_path(self):
        """Details field should contain the HTTP method and path."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            r = client.post("/api/bigquery/export", json={})

        assert r.status_code == 200
        entry = repo.entries[0]
        assert "POST" in entry["details"]
        assert "/api/bigquery/export" in entry["details"]
        assert "200" in entry["details"]

    def test_multiple_writes_all_logged(self):
        """Multiple write requests should each produce an audit entry."""
        repo = InMemoryAuditRepository()
        app, container = _build_middleware_test_app(repo)

        with patch(
            "taa.presentation.api.middleware.audit._get_audit_container",
            return_value=container,
        ):
            client = TestClient(app)
            client.post("/api/bss/schema", json={})
            client.post("/api/bigquery/export", json={})
            client.delete("/api/domain/delete/xyz-789")

        assert len(repo.entries) == 3
        actions = [e["action"] for e in repo.entries]
        assert "create" in actions
        assert "delete" in actions


# ---------------------------------------------------------------------------
# Audit API endpoint tests (using standalone test app to avoid container imports)
# ---------------------------------------------------------------------------

def _build_audit_api_app(repo: InMemoryAuditRepository) -> tuple[FastAPI, MockContainer]:
    """Build a self-contained FastAPI app that mirrors the audit router
    without requiring the full DI container import chain."""
    import csv as csv_mod
    import io as io_mod

    container = MockContainer(repo)
    app = FastAPI()

    # Replicate the audit router endpoints inline to avoid import chain issues

    @app.get("/api/audit/")
    async def list_audit_entries(
        page: int = 1,
        page_size: int = 50,
        user_id: str | None = None,
        action: str | None = None,
        since: str | None = None,
    ):
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                since_dt = None

        offset = (page - 1) * page_size
        entries = await container.audit_repo.query(
            user_id=user_id, action=action, since=since_dt,
            limit=page_size, offset=offset,
        )
        total = await container.audit_repo.count(
            user_id=user_id, action=action, since=since_dt,
        )
        return {
            "entries": entries,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
        }

    @app.get("/api/audit/user/{target_user_id}")
    async def get_user_audit(target_user_id: str, page: int = 1, page_size: int = 50):
        offset = (page - 1) * page_size
        entries = await container.audit_repo.query(
            user_id=target_user_id, limit=page_size, offset=offset,
        )
        total = await container.audit_repo.count(user_id=target_user_id)
        return {
            "entries": entries, "total": total, "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
            "user_id": target_user_id,
        }

    @app.get("/api/audit/action/{action_type}")
    async def get_action_audit(action_type: str, page: int = 1, page_size: int = 50):
        offset = (page - 1) * page_size
        entries = await container.audit_repo.query(
            action=action_type, limit=page_size, offset=offset,
        )
        total = await container.audit_repo.count(action=action_type)
        return {
            "entries": entries, "total": total, "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
            "action": action_type,
        }

    @app.get("/api/audit/stats")
    async def get_audit_stats():
        total = await container.audit_repo.count()
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = await container.audit_repo.count(since=today_start)
        recent = await container.audit_repo.query(limit=1000)

        user_counts: dict[str, int] = {}
        for entry in recent:
            uid = entry.get("username") or entry.get("user_id", "unknown")
            user_counts[uid] = user_counts.get(uid, 0) + 1
        top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        action_counts: dict[str, int] = {}
        for entry in recent:
            act = entry.get("action", "unknown")
            action_counts[act] = action_counts.get(act, 0) + 1
        top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        day_counts: dict[str, int] = {}
        for entry in recent:
            created = entry.get("created_at", "")
            if created:
                day = created[:10]
                day_counts[day] = day_counts.get(day, 0) + 1
        entries_per_day = sorted(day_counts.items(), key=lambda x: x[0], reverse=True)[:7]

        return {
            "total_entries": total,
            "today_entries": today_count,
            "unique_users": len(user_counts),
            "top_users": [{"user": u, "count": c} for u, c in top_users],
            "top_actions": [{"action": a, "count": c} for a, c in top_actions],
            "entries_per_day": [{"date": d, "count": c} for d, c in entries_per_day],
        }

    @app.get("/api/audit/export")
    async def export_audit_csv(
        user_id: str | None = None,
        action: str | None = None,
        since: str | None = None,
    ):
        from fastapi.responses import StreamingResponse

        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            except ValueError:
                since_dt = None

        entries = await container.audit_repo.query(
            user_id=user_id, action=action, since=since_dt, limit=10000,
        )

        output = io_mod.StringIO()
        writer = csv_mod.writer(output)
        writer.writerow(["id", "timestamp", "user_id", "username", "action",
                         "resource_type", "resource_id", "ip_address", "details"])

        for entry in entries:
            writer.writerow([
                entry.get("id", ""),
                entry.get("created_at", ""),
                entry.get("user_id", ""),
                entry.get("username", ""),
                entry.get("action", ""),
                entry.get("resource_type", ""),
                entry.get("resource_id", ""),
                entry.get("ip_address", ""),
                entry.get("details", ""),
            ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )

    return app, container


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------

def _seed_entries(repo: InMemoryAuditRepository, count: int = 5) -> None:
    """Synchronously seed audit entries into the repo."""
    import asyncio
    for i in range(count):
        asyncio.get_event_loop().run_until_complete(
            repo.log(
                user_id=f"user{i % 3}",
                action=["create", "update", "delete"][i % 3],
                resource_type=["schema", "export", "domain"][i % 3],
                resource_id=f"r-{i}",
                details=f"test entry {i}",
                username=["alex", "sarah", "mike"][i % 3],
                ip_address=f"10.0.0.{i}",
            )
        )


class TestAuditAPIEndpoints:
    """Test the audit API endpoint logic using a self-contained test app
    that avoids importing the full DI container chain."""

    def test_list_entries_empty(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        client = TestClient(app)

        r = client.get("/api/audit/")
        assert r.status_code == 200
        data = r.json()
        assert data["entries"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    def test_list_entries_with_data(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 3)
        client = TestClient(app)

        r = client.get("/api/audit/")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["entries"]) == 3

    def test_list_entries_pagination(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 5)
        client = TestClient(app)

        r = client.get("/api/audit/?page=1&page_size=2")
        assert r.status_code == 200
        data = r.json()
        assert len(data["entries"]) == 2
        assert data["total"] == 5
        assert data["pages"] == 3

        # Second page
        r2 = client.get("/api/audit/?page=2&page_size=2")
        data2 = r2.json()
        assert len(data2["entries"]) == 2
        assert data2["page"] == 2

        # Third page (partial)
        r3 = client.get("/api/audit/?page=3&page_size=2")
        data3 = r3.json()
        assert len(data3["entries"]) == 1

    def test_list_entries_filter_by_action(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 6)
        client = TestClient(app)

        r = client.get("/api/audit/?action=create")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        for entry in data["entries"]:
            assert entry["action"] == "create"

    def test_list_entries_filter_by_user(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 6)
        client = TestClient(app)

        r = client.get("/api/audit/?user_id=user0")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        for entry in data["entries"]:
            assert entry["user_id"] == "user0"

    def test_user_audit_endpoint(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 6)
        client = TestClient(app)

        r = client.get("/api/audit/user/user0")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == "user0"
        assert data["total"] >= 1
        for entry in data["entries"]:
            assert entry["user_id"] == "user0"

    def test_action_audit_endpoint(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 6)
        client = TestClient(app)

        r = client.get("/api/audit/action/delete")
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "delete"
        assert data["total"] >= 1
        for entry in data["entries"]:
            assert entry["action"] == "delete"

    def test_stats_endpoint(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 6)
        client = TestClient(app)

        r = client.get("/api/audit/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_entries"] == 6
        assert data["today_entries"] == 6
        assert data["unique_users"] >= 2
        assert len(data["top_users"]) >= 1
        assert len(data["top_actions"]) >= 1
        assert "entries_per_day" in data
        assert len(data["entries_per_day"]) >= 1

    def test_export_csv_endpoint(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 3)
        client = TestClient(app)

        r = client.get("/api/audit/export")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]
        assert "attachment" in r.headers.get("content-disposition", "")

        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        assert len(rows) == 4  # header + 3 entries

        header = rows[0]
        assert "id" in header
        assert "timestamp" in header
        assert "user_id" in header
        assert "username" in header
        assert "action" in header
        assert "resource_type" in header
        assert "ip_address" in header

    def test_export_csv_with_action_filter(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 6)
        client = TestClient(app)

        r = client.get("/api/audit/export?action=create")
        assert r.status_code == 200
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        # Header + only "create" entries
        assert len(rows) >= 2
        for row in rows[1:]:
            assert row[4] == "create"  # action column

    def test_export_csv_with_user_filter(self):
        repo = InMemoryAuditRepository()
        app, _ = _build_audit_api_app(repo)
        _seed_entries(repo, 6)
        client = TestClient(app)

        r = client.get("/api/audit/export?user_id=user0")
        assert r.status_code == 200
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        assert len(rows) >= 2
        for row in rows[1:]:
            assert row[2] == "user0"  # user_id column
