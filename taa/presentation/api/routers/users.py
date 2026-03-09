"""User management CRUD endpoints.

All endpoints require the ``users:manage`` permission (management role).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from taa.presentation.api.auth import (
    UserRecord,
    pwd_context,
    require_permission,
)
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import (
    PasswordResetRequest,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter()

VALID_ROLES = {"user", "admin", "management"}


def _user_dict_to_response(u: dict) -> UserResponse:
    return UserResponse(
        id=str(u["id"]),
        username=u["username"],
        name=u.get("name", ""),
        email=u.get("email", ""),
        role=u.get("role", "user"),
        disabled=bool(u.get("disabled", False)),
        created_at=u.get("created_at"),
        updated_at=u.get("updated_at"),
    )


@router.get("/", response_model=list[UserResponse])
async def list_users(
    current_user: Annotated[UserRecord, Depends(require_permission("users:manage"))],
) -> list[UserResponse]:
    """List all users."""
    container = get_container()
    users = await container.user_repo.list_all()
    return [_user_dict_to_response(u) for u in users]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: Annotated[UserRecord, Depends(require_permission("users:manage"))],
) -> UserResponse:
    """Get a single user by ID."""
    container = get_container()
    user = await container.user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_dict_to_response(user)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    body: UserCreateRequest,
    current_user: Annotated[UserRecord, Depends(require_permission("users:manage"))],
) -> UserResponse:
    """Create a new user."""
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role: {body.role}. Must be one of {sorted(VALID_ROLES)}",
        )

    container = get_container()

    # Check for duplicate username
    existing = await container.user_repo.get_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )

    user_data = {
        "username": body.username,
        "name": body.name,
        "email": body.email,
        "role": body.role,
        "hashed_password": pwd_context.hash(body.password),
        "disabled": False,
    }
    created = await container.user_repo.create(user_data)
    return _user_dict_to_response(created)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    current_user: Annotated[UserRecord, Depends(require_permission("users:manage"))],
) -> UserResponse:
    """Update a user's name, email, role, or password."""
    container = get_container()

    existing = await container.user_repo.get_by_id(user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    fields: dict = {}
    if body.name is not None:
        fields["name"] = body.name
    if body.email is not None:
        fields["email"] = body.email
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {body.role}. Must be one of {sorted(VALID_ROLES)}",
            )
        fields["role"] = body.role
    if body.password is not None:
        fields["hashed_password"] = pwd_context.hash(body.password)

    if not fields:
        return _user_dict_to_response(existing)

    updated = await container.user_repo.update(user_id, fields)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_dict_to_response(updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: Annotated[UserRecord, Depends(require_permission("users:manage"))],
) -> None:
    """Delete a user. Cannot delete yourself."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    container = get_container()
    deleted = await container.user_repo.delete(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.post("/{user_id}/reset-password", response_model=UserResponse)
async def reset_password(
    user_id: str,
    body: PasswordResetRequest,
    current_user: Annotated[UserRecord, Depends(require_permission("users:manage"))],
) -> UserResponse:
    """Admin password reset for a user."""
    container = get_container()

    existing = await container.user_repo.get_by_id(user_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updated = await container.user_repo.update(
        user_id, {"hashed_password": pwd_context.hash(body.new_password)}
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_dict_to_response(updated)
