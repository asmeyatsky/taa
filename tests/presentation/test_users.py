"""Tests for the user management CRUD endpoints (/api/users)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from taa.presentation.api.app import create_app
from taa.presentation.api.auth import create_access_token, verify_password
from taa.presentation.api.dependencies import get_container


@pytest.fixture
def client():
    """Create a test client with a properly initialised in-memory database.

    Uses the ``with`` context manager so the FastAPI lifespan fires,
    which initialises the database and seeds demo users.
    We also clear the ``get_container`` LRU cache so each test gets
    a fresh container pointing at an in-memory SQLite database.
    """
    get_container.cache_clear()

    # Monkey-patch get_container to use an in-memory database
    from taa.infrastructure.config.container import Container

    _container = Container(db_url=":memory:")
    get_container.cache_clear()

    original_fn = get_container.__wrapped__

    def _patched():
        return _container

    # Replace the lru_cache'd function's logic
    get_container.cache_clear()
    import taa.presentation.api.dependencies as deps
    deps.get_container = _patched  # type: ignore[assignment]

    # Also patch where app.py and routers import get_container from
    import taa.presentation.api.app as app_mod
    import taa.presentation.api.routers.users as users_mod
    import taa.presentation.api.auth as auth_mod

    old_app = app_mod.get_container
    old_users = users_mod.get_container
    old_auth_repo = auth_mod._get_user_repo

    app_mod.get_container = _patched  # type: ignore[assignment]
    users_mod.get_container = _patched  # type: ignore[assignment]

    def _patched_get_user_repo():
        c = _patched()
        if c.db.is_available:
            return c.user_repo
        return None

    auth_mod._get_user_repo = _patched_get_user_repo  # type: ignore[assignment]

    app = create_app()
    with TestClient(app) as tc:
        yield tc

    # Restore originals
    app_mod.get_container = old_app  # type: ignore[assignment]
    users_mod.get_container = old_users  # type: ignore[assignment]
    auth_mod._get_user_repo = old_auth_repo  # type: ignore[assignment]
    deps.get_container = get_container  # type: ignore[assignment]
    get_container.cache_clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _login(client: TestClient, username: str, password: str):
    return client.post("/api/auth/token", data={"username": username, "password": password})


def _get_token(client: TestClient, username: str, password: str) -> str:
    r = _login(client, username, password)
    assert r.status_code == 200, f"Login failed for {username}: {r.text}"
    return r.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _mgmt_headers(client: TestClient) -> dict[str, str]:
    """Get auth headers for the management user (mike)."""
    return _auth(_get_token(client, "mike", "director123"))


def _admin_headers(client: TestClient) -> dict[str, str]:
    """Get auth headers for the admin user (sarah)."""
    return _auth(_get_token(client, "sarah", "admin123"))


def _user_headers(client: TestClient) -> dict[str, str]:
    """Get auth headers for the basic user (alex)."""
    return _auth(_get_token(client, "alex", "analyst123"))


# ---------------------------------------------------------------------------
# 1. Permission checks
# ---------------------------------------------------------------------------
class TestUserPermissions:
    def test_list_users_requires_auth(self, client: TestClient):
        r = client.get("/api/users/")
        assert r.status_code == 401

    def test_list_users_forbidden_for_basic_user(self, client: TestClient):
        r = client.get("/api/users/", headers=_user_headers(client))
        assert r.status_code == 403

    def test_list_users_forbidden_for_admin(self, client: TestClient):
        r = client.get("/api/users/", headers=_admin_headers(client))
        assert r.status_code == 403

    def test_list_users_allowed_for_management(self, client: TestClient):
        r = client.get("/api/users/", headers=_mgmt_headers(client))
        assert r.status_code == 200

    def test_create_user_forbidden_for_basic_user(self, client: TestClient):
        r = client.post("/api/users/", json={
            "username": "test", "password": "test123",
        }, headers=_user_headers(client))
        assert r.status_code == 403

    def test_delete_user_forbidden_for_admin(self, client: TestClient):
        r = client.delete("/api/users/1", headers=_admin_headers(client))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 2. List users
# ---------------------------------------------------------------------------
class TestListUsers:
    def test_list_returns_seeded_users(self, client: TestClient):
        r = client.get("/api/users/", headers=_mgmt_headers(client))
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list)
        assert len(users) >= 3  # 3 demo users
        usernames = {u["username"] for u in users}
        assert "alex" in usernames
        assert "sarah" in usernames
        assert "mike" in usernames

    def test_list_does_not_expose_password(self, client: TestClient):
        r = client.get("/api/users/", headers=_mgmt_headers(client))
        for u in r.json():
            assert "hashed_password" not in u
            assert "password" not in u


# ---------------------------------------------------------------------------
# 3. Get single user
# ---------------------------------------------------------------------------
class TestGetUser:
    def test_get_existing_user(self, client: TestClient):
        r = client.get("/api/users/1", headers=_mgmt_headers(client))
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "1"
        assert data["username"] == "alex"
        assert data["role"] == "user"

    def test_get_nonexistent_user(self, client: TestClient):
        r = client.get("/api/users/nonexistent-id", headers=_mgmt_headers(client))
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 4. Create user
# ---------------------------------------------------------------------------
class TestCreateUser:
    def test_create_user_success(self, client: TestClient):
        r = client.post("/api/users/", json={
            "username": "newuser",
            "name": "New User",
            "email": "new@telco.com",
            "role": "user",
            "password": "newpass123",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "newuser"
        assert data["name"] == "New User"
        assert data["email"] == "new@telco.com"
        assert data["role"] == "user"
        assert "id" in data
        assert "hashed_password" not in data

    def test_create_user_can_login(self, client: TestClient):
        """After creating a user via the API, they should be able to log in."""
        client.post("/api/users/", json={
            "username": "logintest",
            "name": "Login Test",
            "email": "login@telco.com",
            "role": "user",
            "password": "mypassword",
        }, headers=_mgmt_headers(client))

        r = _login(client, "logintest", "mypassword")
        assert r.status_code == 200
        assert r.json()["user"]["username"] == "logintest"

    def test_create_duplicate_username(self, client: TestClient):
        r = client.post("/api/users/", json={
            "username": "alex",  # already exists
            "password": "pass123",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 409
        assert "already exists" in r.json()["detail"]

    def test_create_user_invalid_role(self, client: TestClient):
        r = client.post("/api/users/", json={
            "username": "badrole",
            "password": "pass123",
            "role": "superadmin",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 400
        assert "Invalid role" in r.json()["detail"]

    def test_create_user_defaults(self, client: TestClient):
        r = client.post("/api/users/", json={
            "username": "minimaluser",
            "password": "pass123",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 201
        data = r.json()
        assert data["role"] == "user"
        assert data["name"] == ""
        assert data["email"] == ""


# ---------------------------------------------------------------------------
# 5. Update user
# ---------------------------------------------------------------------------
class TestUpdateUser:
    def test_update_name_and_email(self, client: TestClient):
        r = client.put("/api/users/1", json={
            "name": "Alex Updated",
            "email": "alex.updated@telco.com",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Alex Updated"
        assert data["email"] == "alex.updated@telco.com"

    def test_update_role(self, client: TestClient):
        # Create a test user first
        cr = client.post("/api/users/", json={
            "username": "rolechange",
            "password": "pass123",
            "role": "user",
        }, headers=_mgmt_headers(client))
        user_id = cr.json()["id"]

        r = client.put(f"/api/users/{user_id}", json={
            "role": "admin",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_update_password(self, client: TestClient):
        # Create a user
        cr = client.post("/api/users/", json={
            "username": "pwdchange",
            "password": "oldpass",
            "role": "user",
        }, headers=_mgmt_headers(client))
        assert cr.status_code == 201

        user_id = cr.json()["id"]

        # Update password
        r = client.put(f"/api/users/{user_id}", json={
            "password": "newpass",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 200

        # Login with new password should succeed
        lr = _login(client, "pwdchange", "newpass")
        assert lr.status_code == 200

    def test_update_nonexistent_user(self, client: TestClient):
        r = client.put("/api/users/nonexistent", json={
            "name": "Ghost",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 404

    def test_update_invalid_role(self, client: TestClient):
        r = client.put("/api/users/1", json={
            "role": "invalid_role",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 400

    def test_update_no_fields(self, client: TestClient):
        """Updating with no fields should return the existing user unchanged."""
        r = client.put("/api/users/1", json={}, headers=_mgmt_headers(client))
        assert r.status_code == 200
        assert r.json()["id"] == "1"


# ---------------------------------------------------------------------------
# 6. Delete user
# ---------------------------------------------------------------------------
class TestDeleteUser:
    def test_delete_user_success(self, client: TestClient):
        # Create a user to delete
        cr = client.post("/api/users/", json={
            "username": "deleteme",
            "password": "pass123",
        }, headers=_mgmt_headers(client))
        user_id = cr.json()["id"]

        r = client.delete(f"/api/users/{user_id}", headers=_mgmt_headers(client))
        assert r.status_code == 204

        # Verify they're gone
        r2 = client.get(f"/api/users/{user_id}", headers=_mgmt_headers(client))
        assert r2.status_code == 404

    def test_delete_nonexistent_user(self, client: TestClient):
        r = client.delete("/api/users/nonexistent", headers=_mgmt_headers(client))
        assert r.status_code == 404

    def test_delete_self_prevented(self, client: TestClient):
        """Management user (mike, id=3) cannot delete themselves."""
        r = client.delete("/api/users/3", headers=_mgmt_headers(client))
        assert r.status_code == 400
        assert "Cannot delete your own account" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 7. Password reset
# ---------------------------------------------------------------------------
class TestPasswordReset:
    def test_reset_password_success(self, client: TestClient):
        # Create a user
        cr = client.post("/api/users/", json={
            "username": "resetme",
            "password": "oldpassword",
        }, headers=_mgmt_headers(client))
        user_id = cr.json()["id"]

        # Reset their password
        r = client.post(f"/api/users/{user_id}/reset-password", json={
            "new_password": "brandnewpassword",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 200

        # Login with new password
        lr = _login(client, "resetme", "brandnewpassword")
        assert lr.status_code == 200

    def test_reset_password_nonexistent_user(self, client: TestClient):
        r = client.post("/api/users/nonexistent/reset-password", json={
            "new_password": "newpass",
        }, headers=_mgmt_headers(client))
        assert r.status_code == 404

    def test_reset_password_forbidden_for_basic_user(self, client: TestClient):
        r = client.post("/api/users/1/reset-password", json={
            "new_password": "newpass",
        }, headers=_user_headers(client))
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 8. Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_created_user_visible_in_list(self, client: TestClient):
        headers = _mgmt_headers(client)
        client.post("/api/users/", json={
            "username": "visible",
            "password": "pass123",
            "name": "Visible User",
        }, headers=headers)

        r = client.get("/api/users/", headers=headers)
        usernames = {u["username"] for u in r.json()}
        assert "visible" in usernames

    def test_invalid_token_on_all_endpoints(self, client: TestClient):
        bad = _auth("invalid.token.here")
        assert client.get("/api/users/", headers=bad).status_code == 401
        assert client.get("/api/users/1", headers=bad).status_code == 401
        assert client.post("/api/users/", json={"username": "x", "password": "x"}, headers=bad).status_code == 401
        assert client.put("/api/users/1", json={"name": "x"}, headers=bad).status_code == 401
        assert client.delete("/api/users/1", headers=bad).status_code == 401
        assert client.post("/api/users/1/reset-password", json={"new_password": "x"}, headers=bad).status_code == 401

    def test_create_all_roles(self, client: TestClient):
        """Can create users with each valid role."""
        headers = _mgmt_headers(client)
        for role in ("user", "admin", "management"):
            r = client.post("/api/users/", json={
                "username": f"role_{role}",
                "password": "pass123",
                "role": role,
            }, headers=headers)
            assert r.status_code == 201
            assert r.json()["role"] == role
