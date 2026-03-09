"""JWT authentication for TAA API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# Config — in production these come from env vars
SECRET_KEY = os.getenv("TAA_SECRET_KEY", "taa-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TAA_TOKEN_EXPIRE_MINUTES", "480"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


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


# Role definitions
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
    ],
    "management": [
        "domains:view", "generate:run", "generate:download",
        "compliance:view", "compliance:run", "compliance:export",
        "analytics:view", "analytics:generate",
        "bss:upload_schema", "mock:generate",
        "users:manage", "audit:view", "settings:manage",
    ],
}

# Demo user store — in production this would be a database
USERS_DB: dict[str, UserRecord] = {
    "alex": UserRecord(
        id="1", username="alex", name="Alex Analyst",
        email="alex@telco.com", role="user",
        hashed_password=pwd_context.hash("analyst123"),
    ),
    "sarah": UserRecord(
        id="2", username="sarah", name="Sarah Admin",
        email="sarah@telco.com", role="admin",
        hashed_password=pwd_context.hash("admin123"),
    ),
    "mike": UserRecord(
        id="3", username="mike", name="Mike Director",
        email="mike@telco.com", role="management",
        hashed_password=pwd_context.hash("director123"),
    ),
}


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def authenticate_user(username: str, password: str) -> UserRecord | None:
    user = USERS_DB.get(username)
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
        user = USERS_DB.get(username)
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
