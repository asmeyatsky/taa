"""Authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from taa.presentation.api.auth import (
    ROLES,
    authenticate_user,
    create_access_token,
    get_current_user,
    TokenResponse,
    UserOut,
    UserRecord,
)

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    """Authenticate and return a JWT token."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(data={"sub": user.username, "role": user.role})
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user.id, username=user.username,
            name=user.name, email=user.email, role=user.role,
        ),
    )


@router.get("/me", response_model=UserOut)
def get_me(user: Annotated[UserRecord, Depends(get_current_user)]) -> UserOut:
    """Get current authenticated user."""
    return UserOut(
        id=user.id, username=user.username,
        name=user.name, email=user.email, role=user.role,
    )


@router.get("/permissions")
def get_my_permissions(user: Annotated[UserRecord, Depends(get_current_user)]) -> dict:
    """Get permissions for the current user's role."""
    return {
        "role": user.role,
        "permissions": ROLES.get(user.role, []),
    }
