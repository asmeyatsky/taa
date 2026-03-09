"""JWT authentication for TAA API.

Supports two modes:
- **Database mode**: when the SQLite database is available, users are
  loaded from / persisted to the ``users`` table.
- **In-memory fallback**: when the database is unavailable, a static
  ``USERS_DB`` dict is used (identical to the original behaviour).

Demo users are defined in ``DEMO_USERS`` and seeded into the database
on first application startup (see ``app.py``).
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Config -- in production these come from env vars
SECRET_KEY = os.getenv("TAA_SECRET_KEY", "taa-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TAA_TOKEN_EXPIRE_MINUTES", "480"))

# Default organization for demo users
DEFAULT_ORG_ID = "org-demo"
DEFAULT_ORG_NAME = "Demo"
DEFAULT_ORG_SLUG = "demo"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# ------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------

class Role(BaseModel):
    name: str
    permissions: list[str]


class UserRecord(BaseModel):
    id: str
    username: str
    name: str
    email: str
    role: str
    hashed_password: str
    disabled: bool = False
    org_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserOut(BaseModel):
    id: str
    username: str
    name: str
    email: str
    role: str
    org_id: str | None = None


# ------------------------------------------------------------------
# Role definitions
# ------------------------------------------------------------------

ROLES: dict[str, list[str]] = {
    "user": [
        "domains:view", "generate:run", "generate:download",
        "compliance:view", "analytics:view", "analytics:generate",
    ],
    "admin": [
        "domains:view", "generate:run", "generate:download",
        "compliance:view", "compliance:run", "compliance:export",
        "analytics:view", "analytics:generate",
        "bss:upload_schema", "mock:generate", "audit:view", "settings:manage",
        "orgs:view",
    ],
    "management": [
        "domains:view", "generate:run", "generate:download",
        "compliance:view", "compliance:run", "compliance:export",
        "analytics:view", "analytics:generate",
        "bss:upload_schema", "mock:generate",
        "users:manage", "audit:view", "settings:manage",
        "orgs:view", "orgs:manage",
    ],
}


# ------------------------------------------------------------------
# Demo users (seed data)
# ------------------------------------------------------------------

DEMO_USERS: list[dict[str, Any]] = [
    {
        "id": "1", "username": "alex", "name": "Alex Analyst",
        "email": "alex@telco.com", "role": "user",
        "hashed_password": pwd_context.hash("analyst123"),
        "disabled": False,
        "org_id": DEFAULT_ORG_ID,
    },
    {
        "id": "2", "username": "sarah", "name": "Sarah Admin",
        "email": "sarah@telco.com", "role": "admin",
        "hashed_password": pwd_context.hash("admin123"),
        "disabled": False,
        "org_id": DEFAULT_ORG_ID,
    },
    {
        "id": "3", "username": "mike", "name": "Mike Director",
        "email": "mike@telco.com", "role": "management",
        "hashed_password": pwd_context.hash("director123"),
        "disabled": False,
        "org_id": DEFAULT_ORG_ID,
    },
]

# In-memory fallback store, built from DEMO_USERS
USERS_DB: dict[str, UserRecord] = {
    u["username"]: UserRecord(**u) for u in DEMO_USERS
}


# ------------------------------------------------------------------
# Helpers to bridge sync FastAPI endpoints with async DB repository
# ------------------------------------------------------------------

def _get_user_repo():
    """Return the user repository from the DI container, or None if unavailable."""
    from taa.presentation.api.dependencies import get_container
    container = get_container()
    if container.db.is_available:
        return container.user_repo
    return None


def _run_async(coro):
    """Run an async coroutine from synchronous code.

    Works whether or not there is a running event loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # We are inside an async context (e.g. FastAPI with async event loop).
        # Create a new thread to run the coroutine without blocking.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def _dict_to_record(d: dict[str, Any]) -> UserRecord:
    """Convert a database row dict to a UserRecord."""
    return UserRecord(
        id=str(d["id"]),
        username=d["username"],
        name=d.get("name", ""),
        email=d.get("email", ""),
        role=d.get("role", "user"),
        hashed_password=d["hashed_password"],
        disabled=bool(d.get("disabled", False)),
        org_id=d.get("org_id"),
    )


# ------------------------------------------------------------------
# Core auth functions
# ------------------------------------------------------------------

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _lookup_user(username: str) -> UserRecord | None:
    """Look up a user by username, trying DB first then in-memory fallback."""
    repo = _get_user_repo()
    if repo is not None:
        try:
            row = _run_async(repo.get_by_username(username))
            if row is not None:
                return _dict_to_record(row)
        except Exception:
            logger.debug("DB lookup failed, falling back to in-memory", exc_info=True)
    return USERS_DB.get(username)


def authenticate_user(username: str, password: str) -> UserRecord | None:
    user = _lookup_user(username)
    if not user or user.disabled:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user_optional(token: Annotated[str | None, Depends(oauth2_scheme)]) -> UserRecord | None:
    """Return current user if token present and valid, else None."""
    if token is None:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            return None
        user = _lookup_user(username)
        if user is None or user.disabled:
            return None
        return user
    except JWTError:
        return None


def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)]) -> UserRecord:
    """Require a valid authenticated user."""
    user = get_current_user_optional(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_permission(permission: str):
    """Dependency factory that checks a specific permission."""
    def checker(user: Annotated[UserRecord, Depends(get_current_user)]) -> UserRecord:
        user_perms = ROLES.get(user.role, [])
        if permission not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return user
    return checker
