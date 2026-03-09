"""Tenant context for multi-tenant request isolation.

Uses ``contextvars`` for async-safe per-request tenant state.
Provides a FastAPI dependency ``get_current_tenant`` that returns
the resolved tenant ID for the current request.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status


# Async-safe context variable holding the tenant ID for the current request.
_tenant_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "tenant_id", default=None
)


@dataclass
class TenantContext:
    """Resolved tenant information for the current request."""

    org_id: str
    org_name: str | None = None
    org_plan: str | None = None


def set_current_tenant(org_id: str | None) -> None:
    """Set the tenant ID in the async context."""
    _tenant_ctx.set(org_id)


def get_tenant_id() -> str | None:
    """Get the tenant ID from the async context."""
    return _tenant_ctx.get()


def clear_tenant() -> None:
    """Clear the tenant context (e.g. at end of request)."""
    _tenant_ctx.set(None)


async def get_current_tenant(request: Request) -> str | None:
    """FastAPI dependency that returns the current tenant ID.

    Reads from the request state which is set by TenantMiddleware.
    Returns None for unauthenticated / tenant-free requests.
    """
    return getattr(request.state, "tenant_id", None)


async def require_tenant(request: Request) -> str:
    """FastAPI dependency that requires a valid tenant.

    Raises 403 if no tenant is set on the request.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant context required",
        )
    return tenant_id
