"""Comprehensive tests for the TAA JWT authentication system."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from taa.presentation.api.app import create_app
from taa.presentation.api.auth import (
    ALGORITHM,
    ROLES,
    SECRET_KEY,
    USERS_DB,
    authenticate_user,
    create_access_token,
    verify_password,
)


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def _login(client: TestClient, username: str, password: str):
    """Helper: perform a login and return the response."""
    return client.post(
        "/api/auth/token",
        data={"username": username, "password": password},
    )


def _auth_header(token: str) -> dict[str, str]:
    """Helper: build an Authorization header."""
    return {"Authorization": f"Bearer {token}"}


def _get_token(client: TestClient, username: str, password: str) -> str:
    """Helper: login and return just the access_token string."""
    r = _login(client, username, password)
    assert r.status_code == 200
    return r.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. Password verification
# ---------------------------------------------------------------------------
class TestVerifyPassword:
    def test_correct_password(self):
        user = USERS_DB["alex"]
        assert verify_password("analyst123", user.hashed_password) is True

    def test_wrong_password(self):
        user = USERS_DB["alex"]
        assert verify_password("wrongpassword", user.hashed_password) is False

    def test_empty_password(self):
        user = USERS_DB["alex"]
        assert verify_password("", user.hashed_password) is False


# ---------------------------------------------------------------------------
# 2. authenticate_user function
# ---------------------------------------------------------------------------
class TestAuthenticateUser:
    def test_valid_credentials(self):
        user = authenticate_user("alex", "analyst123")
        assert user is not None
        assert user.username == "alex"
        assert user.role == "user"

    def test_valid_admin_credentials(self):
        user = authenticate_user("sarah", "admin123")
        assert user is not None
        assert user.username == "sarah"
        assert user.role == "admin"

    def test_valid_management_credentials(self):
        user = authenticate_user("mike", "director123")
        assert user is not None
        assert user.username == "mike"
        assert user.role == "management"

    def test_wrong_password_returns_none(self):
        assert authenticate_user("alex", "badpassword") is None

    def test_nonexistent_user_returns_none(self):
        assert authenticate_user("nobody", "password") is None

    def test_disabled_user_returns_none(self):
        # Temporarily disable a user
        original = USERS_DB["alex"].disabled
        try:
            USERS_DB["alex"].disabled = True
            assert authenticate_user("alex", "analyst123") is None
        finally:
            USERS_DB["alex"].disabled = original


# ---------------------------------------------------------------------------
# 3. Token creation and validation
# ---------------------------------------------------------------------------
class TestCreateAccessToken:
    def test_token_contains_subject(self):
        token = create_access_token(data={"sub": "alex", "role": "user"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "alex"
        assert payload["role"] == "user"

    def test_token_contains_expiry(self):
        token = create_access_token(data={"sub": "alex"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_token_custom_expiry(self):
        token = create_access_token(
            data={"sub": "alex"},
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in payload

    def test_token_decodes_with_correct_secret(self):
        token = create_access_token(data={"sub": "sarah"})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "sarah"

    def test_token_fails_with_wrong_secret(self):
        token = create_access_token(data={"sub": "sarah"})
        with pytest.raises(Exception):
            jwt.decode(token, "wrong-secret", algorithms=[ALGORITHM])

    def test_expired_token_raises(self):
        token = create_access_token(
            data={"sub": "alex"},
            expires_delta=timedelta(seconds=-1),
        )
        with pytest.raises(Exception):
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ---------------------------------------------------------------------------
# 4. POST /api/auth/token — login endpoint
# ---------------------------------------------------------------------------
class TestLoginEndpoint:
    def test_login_success_user(self, client: TestClient):
        r = _login(client, "alex", "analyst123")
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["username"] == "alex"
        assert body["user"]["role"] == "user"
        assert body["user"]["email"] == "alex@telco.com"
        assert body["user"]["name"] == "Alex Analyst"
        assert body["user"]["id"] == "1"

    def test_login_success_admin(self, client: TestClient):
        r = _login(client, "sarah", "admin123")
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["username"] == "sarah"
        assert body["user"]["role"] == "admin"

    def test_login_success_management(self, client: TestClient):
        r = _login(client, "mike", "director123")
        assert r.status_code == 200
        body = r.json()
        assert body["user"]["username"] == "mike"
        assert body["user"]["role"] == "management"

    def test_login_wrong_password(self, client: TestClient):
        r = _login(client, "alex", "wrong")
        assert r.status_code == 401
        assert r.json()["detail"] == "Invalid username or password"

    def test_login_nonexistent_user(self, client: TestClient):
        r = _login(client, "nonexistent", "password")
        assert r.status_code == 401

    def test_login_empty_credentials(self, client: TestClient):
        r = _login(client, "", "")
        # FastAPI/OAuth2 form validation may return 422 for empty fields
        # or 401 if it reaches authenticate_user; both are acceptable rejections
        assert r.status_code in (401, 422)

    def test_login_returns_valid_jwt(self, client: TestClient):
        r = _login(client, "alex", "analyst123")
        token = r.json()["access_token"]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "alex"
        assert payload["role"] == "user"


# ---------------------------------------------------------------------------
# 5. GET /api/auth/me — current user endpoint
# ---------------------------------------------------------------------------
class TestMeEndpoint:
    def test_me_with_valid_token(self, client: TestClient):
        token = _get_token(client, "alex", "analyst123")
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "alex"
        assert body["name"] == "Alex Analyst"
        assert body["email"] == "alex@telco.com"
        assert body["role"] == "user"
        assert body["id"] == "1"

    def test_me_without_token(self, client: TestClient):
        r = client.get("/api/auth/me")
        assert r.status_code == 401
        assert r.json()["detail"] == "Not authenticated"

    def test_me_with_invalid_token(self, client: TestClient):
        r = client.get("/api/auth/me", headers=_auth_header("invalid.jwt.token"))
        assert r.status_code == 401

    def test_me_with_expired_token(self, client: TestClient):
        token = create_access_token(
            data={"sub": "alex", "role": "user"},
            expires_delta=timedelta(seconds=-1),
        )
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 401

    def test_me_with_token_for_nonexistent_user(self, client: TestClient):
        token = create_access_token(data={"sub": "ghost", "role": "user"})
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 401

    def test_me_with_token_missing_sub(self, client: TestClient):
        token = create_access_token(data={"role": "user"})
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 401

    def test_me_with_malformed_bearer_header(self, client: TestClient):
        r = client.get("/api/auth/me", headers={"Authorization": "NotBearer abc"})
        assert r.status_code == 401

    def test_me_admin_user(self, client: TestClient):
        token = _get_token(client, "sarah", "admin123")
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    def test_me_management_user(self, client: TestClient):
        token = _get_token(client, "mike", "director123")
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 200
        assert r.json()["role"] == "management"

    def test_me_disabled_user_token(self, client: TestClient):
        """A token minted before the user was disabled should be rejected."""
        token = _get_token(client, "alex", "analyst123")
        original = USERS_DB["alex"].disabled
        try:
            USERS_DB["alex"].disabled = True
            r = client.get("/api/auth/me", headers=_auth_header(token))
            assert r.status_code == 401
        finally:
            USERS_DB["alex"].disabled = original


# ---------------------------------------------------------------------------
# 6. GET /api/auth/permissions — permissions endpoint
# ---------------------------------------------------------------------------
class TestPermissionsEndpoint:
    def test_permissions_user_role(self, client: TestClient):
        token = _get_token(client, "alex", "analyst123")
        r = client.get("/api/auth/permissions", headers=_auth_header(token))
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "user"
        assert set(body["permissions"]) == set(ROLES["user"])

    def test_permissions_admin_role(self, client: TestClient):
        token = _get_token(client, "sarah", "admin123")
        r = client.get("/api/auth/permissions", headers=_auth_header(token))
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "admin"
        assert set(body["permissions"]) == set(ROLES["admin"])

    def test_permissions_management_role(self, client: TestClient):
        token = _get_token(client, "mike", "director123")
        r = client.get("/api/auth/permissions", headers=_auth_header(token))
        assert r.status_code == 200
        body = r.json()
        assert body["role"] == "management"
        assert set(body["permissions"]) == set(ROLES["management"])

    def test_permissions_without_token(self, client: TestClient):
        r = client.get("/api/auth/permissions")
        assert r.status_code == 401

    def test_permissions_with_invalid_token(self, client: TestClient):
        r = client.get("/api/auth/permissions", headers=_auth_header("bad"))
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 7. Role-based permission matrix validation
# ---------------------------------------------------------------------------
class TestRolePermissionMatrix:
    """Validate the ROLES dict represents a correct permission hierarchy."""

    def test_user_has_basic_permissions(self):
        perms = ROLES["user"]
        assert "domains:view" in perms
        assert "generate:run" in perms
        assert "generate:download" in perms
        assert "compliance:view" in perms
        assert "analytics:view" in perms
        assert "analytics:generate" in perms

    def test_user_lacks_admin_permissions(self):
        perms = ROLES["user"]
        assert "settings:manage" not in perms
        assert "audit:view" not in perms
        assert "bss:upload_schema" not in perms
        assert "mock:generate" not in perms
        assert "compliance:run" not in perms

    def test_admin_has_user_permissions_plus_more(self):
        user_perms = set(ROLES["user"])
        admin_perms = set(ROLES["admin"])
        assert user_perms.issubset(admin_perms), (
            f"Admin should have all user permissions. Missing: {user_perms - admin_perms}"
        )

    def test_admin_has_elevated_permissions(self):
        perms = ROLES["admin"]
        assert "settings:manage" in perms
        assert "audit:view" in perms
        assert "bss:upload_schema" in perms
        assert "mock:generate" in perms
        assert "compliance:run" in perms
        assert "compliance:export" in perms

    def test_admin_lacks_management_only_permissions(self):
        perms = ROLES["admin"]
        assert "users:manage" not in perms

    def test_management_has_user_permissions(self):
        user_perms = set(ROLES["user"])
        mgmt_perms = set(ROLES["management"])
        assert user_perms.issubset(mgmt_perms), (
            f"Management should have all user permissions. Missing: {user_perms - mgmt_perms}"
        )

    def test_management_has_users_manage(self):
        assert "users:manage" in ROLES["management"]

    def test_all_roles_exist(self):
        assert "user" in ROLES
        assert "admin" in ROLES
        assert "management" in ROLES

    def test_all_demo_users_have_valid_roles(self):
        for username, record in USERS_DB.items():
            assert record.role in ROLES, f"User {username} has unknown role {record.role}"


# ---------------------------------------------------------------------------
# 8. require_permission — permission-based access control
# ---------------------------------------------------------------------------
class TestRequirePermission:
    """Test the require_permission dependency by hitting real endpoints
    that use it, or by constructing a mini-app with a guarded route."""

    def _build_guarded_client(self, permission: str) -> TestClient:
        """Build a small FastAPI app with a single endpoint guarded by permission."""
        from fastapi import Depends, FastAPI

        from taa.presentation.api.auth import require_permission
        from taa.presentation.api.routers import auth as auth_router

        app = FastAPI()
        app.include_router(auth_router.router, prefix="/api/auth")

        @app.get("/guarded")
        def guarded(user=Depends(require_permission(permission))):
            return {"ok": True, "user": user.username}

        return TestClient(app)

    def test_user_allowed_when_has_permission(self):
        tc = self._build_guarded_client("domains:view")
        token = _get_token(tc, "alex", "analyst123")
        r = tc.get("/guarded", headers=_auth_header(token))
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_user_denied_when_lacks_permission(self):
        tc = self._build_guarded_client("settings:manage")
        token = _get_token(tc, "alex", "analyst123")
        r = tc.get("/guarded", headers=_auth_header(token))
        assert r.status_code == 403
        assert "Permission denied" in r.json()["detail"]

    def test_admin_can_access_admin_only_permission(self):
        tc = self._build_guarded_client("settings:manage")
        token = _get_token(tc, "sarah", "admin123")
        r = tc.get("/guarded", headers=_auth_header(token))
        assert r.status_code == 200

    def test_management_can_access_users_manage(self):
        tc = self._build_guarded_client("users:manage")
        token = _get_token(tc, "mike", "director123")
        r = tc.get("/guarded", headers=_auth_header(token))
        assert r.status_code == 200

    def test_admin_denied_users_manage(self):
        tc = self._build_guarded_client("users:manage")
        token = _get_token(tc, "sarah", "admin123")
        r = tc.get("/guarded", headers=_auth_header(token))
        assert r.status_code == 403

    def test_no_token_returns_401(self):
        tc = self._build_guarded_client("domains:view")
        r = tc.get("/guarded")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self):
        tc = self._build_guarded_client("domains:view")
        r = tc.get("/guarded", headers=_auth_header("garbage"))
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 9. Token expiry edge cases
# ---------------------------------------------------------------------------
class TestTokenExpiry:
    def test_token_with_zero_expiry_is_rejected(self, client: TestClient):
        token = create_access_token(
            data={"sub": "alex", "role": "user"},
            expires_delta=timedelta(seconds=-10),
        )
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 401

    def test_token_with_large_expiry_is_accepted(self, client: TestClient):
        token = create_access_token(
            data={"sub": "alex", "role": "user"},
            expires_delta=timedelta(days=365),
        )
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 200
        assert r.json()["username"] == "alex"

    def test_default_expiry_token_works(self, client: TestClient):
        token = create_access_token(data={"sub": "sarah", "role": "admin"})
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 10. JWT payload edge cases
# ---------------------------------------------------------------------------
class TestJWTEdgeCases:
    def test_token_signed_with_different_algorithm(self, client: TestClient):
        """A token signed with HS384 should be rejected when HS256 is expected."""
        import datetime

        payload = {
            "sub": "alex",
            "role": "user",
            "exp": datetime.datetime.now(datetime.timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS384")
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 401

    def test_token_with_wrong_secret(self, client: TestClient):
        import datetime

        payload = {
            "sub": "alex",
            "role": "user",
            "exp": datetime.datetime.now(datetime.timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, "totally-wrong-key", algorithm=ALGORITHM)
        r = client.get("/api/auth/me", headers=_auth_header(token))
        assert r.status_code == 401

    def test_empty_bearer_token(self, client: TestClient):
        r = client.get("/api/auth/me", headers={"Authorization": "Bearer "})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 11. Full end-to-end login flow
# ---------------------------------------------------------------------------
class TestEndToEndFlow:
    def test_login_then_me_then_permissions(self, client: TestClient):
        """Full round-trip: login -> /me -> /permissions."""
        # Step 1: Login
        login_r = _login(client, "sarah", "admin123")
        assert login_r.status_code == 200
        token = login_r.json()["access_token"]

        # Step 2: Get current user
        me_r = client.get("/api/auth/me", headers=_auth_header(token))
        assert me_r.status_code == 200
        assert me_r.json()["username"] == "sarah"

        # Step 3: Check permissions
        perm_r = client.get("/api/auth/permissions", headers=_auth_header(token))
        assert perm_r.status_code == 200
        assert perm_r.json()["role"] == "admin"
        assert "settings:manage" in perm_r.json()["permissions"]

    def test_each_demo_user_full_flow(self, client: TestClient):
        """Every demo user can login, hit /me, and get correct permissions."""
        demo_users = [
            ("alex", "analyst123", "user"),
            ("sarah", "admin123", "admin"),
            ("mike", "director123", "management"),
        ]
        for username, password, expected_role in demo_users:
            token = _get_token(client, username, password)
            me = client.get("/api/auth/me", headers=_auth_header(token)).json()
            assert me["username"] == username
            assert me["role"] == expected_role

            perms = client.get("/api/auth/permissions", headers=_auth_header(token)).json()
            assert perms["role"] == expected_role
            assert set(perms["permissions"]) == set(ROLES[expected_role])
