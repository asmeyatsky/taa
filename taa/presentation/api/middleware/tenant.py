"""Tenant resolution middleware for multi-tenant isolation.

Resolves the current tenant from:
1. X-Tenant-ID header (for API clients)
2. JWT token claims (org_id in token payload)

Sets the tenant context on the request state and in the
async-safe contextvars for downstream access.
"""

from __future__ import annotations

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

from taa.presentation.api.tenant import set_current_tenant, clear_tenant

logger = logging.getLogger(__name__)

# Paths that do not require tenant resolution
_TENANT_EXEMPT_PREFIXES = (
    "/api/health",
    "/api/auth/token",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/redoc",
)


class TenantMiddleware(BaseHTTPMiddleware):
    """Resolve tenant context from request headers or JWT claims."""

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str = "",
        algorithm: str = "HS256",
    ) -> None:
        super().__init__(app)
        self._secret_key = secret_key
        self._algorithm = algorithm

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip tenant resolution for exempt paths
        path = request.url.path
        if any(path.startswith(prefix) for prefix in _TENANT_EXEMPT_PREFIXES):
            return await call_next(request)

        tenant_id: str | None = None
        jwt_org_id: str | None = None

        # 1. Check X-Tenant-ID header
        header_tenant = request.headers.get("X-Tenant-ID")

        # 2. Extract org_id from JWT token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer ") and self._secret_key:
            token = auth_header[7:]
            try:
                payload = jwt.decode(token, self._secret_key, algorithms=[self._algorithm])
                jwt_org_id = payload.get("org_id")
            except JWTError:
                pass  # Token validation is handled by the auth layer

        # Resolve tenant: JWT org_id is authoritative
        if header_tenant and jwt_org_id:
            # Header must match the JWT claim — no cross-tenant access
            if header_tenant != jwt_org_id:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Tenant mismatch: X-Tenant-ID header does not match token org_id"
                    },
                )
            tenant_id = jwt_org_id
        elif header_tenant and not jwt_org_id:
            # Reject header-only tenant claims from unauthenticated requests
            # to prevent tenant spoofing
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "X-Tenant-ID header requires authenticated request"
                },
            )
        elif jwt_org_id:
            tenant_id = jwt_org_id

        # Set tenant context
        request.state.tenant_id = tenant_id
        set_current_tenant(tenant_id)

        try:
            response = await call_next(request)
            return response
        finally:
            clear_tenant()
