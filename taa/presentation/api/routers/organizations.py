"""Organization management endpoints for multi-tenant support."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from taa.presentation.api.auth import (
    get_current_user,
    require_permission,
    UserRecord,
    pwd_context,
)
from taa.presentation.api.dependencies import get_container

router = APIRouter()


# ------------------------------------------------------------------
# Request / response models
# ------------------------------------------------------------------

class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    plan: str = Field(default="free", pattern=r"^(free|pro|enterprise)$")
    max_users: int = Field(default=5, ge=1, le=1000)


class UpdateOrgRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    plan: str | None = Field(default=None, pattern=r"^(free|pro|enterprise)$")
    max_users: int | None = Field(default=None, ge=1, le=1000)
    is_active: bool | None = None


class InviteUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    name: str = Field(default="", max_length=100)
    email: str = Field(default="", max_length=200)
    role: str = Field(default="user", pattern=r"^(user|admin|management)$")
    password: str = Field(min_length=6, max_length=100)


class OrgOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    max_users: int
    is_active: bool
    created_at: str


class OrgUserOut(BaseModel):
    id: str
    username: str
    name: str
    email: str
    role: str


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("/", response_model=list[OrgOut])
async def list_organizations(
    user: Annotated[UserRecord, Depends(require_permission("orgs:manage"))],
) -> list[OrgOut]:
    """List all organizations (management only)."""
    container = get_container()
    orgs = await container.org_repo.list_all()
    return [_org_to_out(o) for o in orgs]


@router.post("/", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: CreateOrgRequest,
    user: Annotated[UserRecord, Depends(require_permission("orgs:manage"))],
) -> OrgOut:
    """Create a new organization."""
    container = get_container()

    # Check slug uniqueness
    existing = await container.org_repo.get_by_slug(body.slug)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Organization with slug '{body.slug}' already exists",
        )

    org = await container.org_repo.create({
        "id": str(uuid.uuid4()),
        "name": body.name,
        "slug": body.slug,
        "plan": body.plan,
        "max_users": body.max_users,
    })
    return _org_to_out(org)


@router.get("/{org_id}", response_model=OrgOut)
async def get_organization(
    org_id: str,
    user: Annotated[UserRecord, Depends(require_permission("orgs:view"))],
) -> OrgOut:
    """Get organization details."""
    container = get_container()
    org = await container.org_repo.get_by_id(org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return _org_to_out(org)


@router.put("/{org_id}", response_model=OrgOut)
async def update_organization(
    org_id: str,
    body: UpdateOrgRequest,
    user: Annotated[UserRecord, Depends(require_permission("orgs:manage"))],
) -> OrgOut:
    """Update organization settings."""
    container = get_container()

    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )

    updated = await container.org_repo.update(org_id, fields)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    return _org_to_out(updated)


@router.get("/{org_id}/users", response_model=list[OrgUserOut])
async def list_org_users(
    org_id: str,
    user: Annotated[UserRecord, Depends(require_permission("orgs:view"))],
) -> list[OrgUserOut]:
    """List users belonging to an organization."""
    container = get_container()

    # Verify org exists
    org = await container.org_repo.get_by_id(org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    users = await container.user_repo.list_all(org_id=org_id)
    return [
        OrgUserOut(
            id=u["id"],
            username=u["username"],
            name=u.get("name", ""),
            email=u.get("email", ""),
            role=u.get("role", "user"),
        )
        for u in users
    ]


@router.post("/{org_id}/invite", response_model=OrgUserOut, status_code=status.HTTP_201_CREATED)
async def invite_user_to_org(
    org_id: str,
    body: InviteUserRequest,
    user: Annotated[UserRecord, Depends(require_permission("orgs:manage"))],
) -> OrgUserOut:
    """Invite (create) a user within an organization."""
    container = get_container()

    # Verify org exists and is active
    org = await container.org_repo.get_by_id(org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if not org.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is inactive",
        )

    # Check user limit
    current_users = await container.user_repo.list_all(org_id=org_id)
    max_users = org.get("max_users", 5)
    if len(current_users) >= max_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Organization has reached its user limit ({max_users})",
        )

    # Check username uniqueness
    existing = await container.user_repo.get_by_username(body.username)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )

    new_user = await container.user_repo.create({
        "id": str(uuid.uuid4()),
        "username": body.username,
        "name": body.name,
        "email": body.email,
        "role": body.role,
        "hashed_password": pwd_context.hash(body.password),
        "org_id": org_id,
    })

    return OrgUserOut(
        id=new_user["id"],
        username=new_user["username"],
        name=new_user.get("name", ""),
        email=new_user.get("email", ""),
        role=new_user.get("role", "user"),
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _org_to_out(org: dict[str, Any]) -> OrgOut:
    return OrgOut(
        id=org["id"],
        name=org["name"],
        slug=org["slug"],
        plan=org.get("plan", "free"),
        max_users=org.get("max_users", 5),
        is_active=bool(org.get("is_active", True)),
        created_at=org.get("created_at", ""),
    )
