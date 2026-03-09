"""Audit logging middleware for TAA API.

Intercepts write operations (POST, PUT, DELETE) on key endpoints and
records them to the audit_log table via AuditRepository.  GET requests,
health checks, and metrics endpoints are silently skipped.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from fastapi import Request, Response
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# HTTP methods that represent write operations
_WRITE_METHODS = {"POST", "PUT", "DELETE", "PATCH"}

# Paths that should never be audited
_SKIP_PATHS = {
    "/api/health",
    "/metrics",
    "/api/auth/token",
    "/docs",
    "/openapi.json",
    "/redoc",
}

# Prefixes that should never be audited
_SKIP_PREFIXES = (
    "/api/health",
    "/metrics",
)

# Map URL path patterns to (resource_type, action_verb)
_PATH_RESOURCE_MAP: list[tuple[str, str, str]] = [
    # (regex pattern, resource_type, default action override or empty)
    (r"/api/auth/", "auth", ""),
    (r"/api/bss/schema", "schema", ""),
    (r"/api/bss/", "bss", ""),
    (r"/api/domain/ldm", "domain", ""),
    (r"/api/domain/", "domain", ""),
    (r"/api/bigquery/export", "export", ""),
    (r"/api/bigquery/", "bigquery", ""),
    (r"/api/compliance/", "compliance", ""),
    (r"/api/analytics/", "analytics", ""),
    (r"/api/mock/", "mock", ""),
    (r"/api/audit/", "audit", ""),
]


_REDACT_PII = os.getenv("TAA_LOG_REDACT_PII", "false").lower() == "true"


def _extract_client_ip(request: Request) -> str:
    """Extract the client IP from the request, optionally redacted."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = "unknown"
    if _REDACT_PII and ip != "unknown":
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.***"
        return "***"
    return ip


def _classify_request(method: str, path: str) -> tuple[str, str, str | None]:
    """Classify a request into (action, resource_type, resource_id).

    Returns action like 'create', 'update', 'delete' based on HTTP method,
    and resource_type based on URL path pattern.
    """
    # Determine action from HTTP method
    action_map = {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    action = action_map.get(method, method.lower())

    # Determine resource type from path
    resource_type = "unknown"
    for pattern, rtype, action_override in _PATH_RESOURCE_MAP:
        if re.search(pattern, path):
            resource_type = rtype
            if action_override:
                action = action_override
            break

    # Try to extract a resource ID from the path (last segment if it looks like an ID)
    resource_id = None
    parts = path.rstrip("/").split("/")
    if len(parts) > 3:
        last = parts[-1]
        # If the last segment looks like an ID (UUID-like or numeric)
        if len(last) > 4 and any(c.isdigit() for c in last):
            resource_id = last

    return action, resource_type, resource_id


def _extract_user_from_token(request: Request) -> tuple[str, str]:
    """Extract user_id and username from the JWT token in the request.

    Returns (user_id, username).  Falls back to ("anonymous", "anonymous")
    if no valid token is present.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return "anonymous", "anonymous"

    token = auth_header[7:]
    try:
        from taa.presentation.api.auth import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub", "unknown")
        # The user ID is not stored in the JWT payload by default,
        # so we use the username as the user_id fallback
        user_id = payload.get("user_id", username)
        return str(user_id), str(username)
    except (JWTError, Exception):
        return "anonymous", "anonymous"


def _get_audit_container():
    """Lazy import helper for the DI container.

    Defined at module level so tests can patch it easily via
    ``taa.presentation.api.middleware.audit._get_audit_container``.
    """
    from taa.presentation.api.dependencies import get_container
    return get_container()


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware that logs write operations to the audit log.

    Only POST, PUT, DELETE, and PATCH requests are logged.
    GET requests, health checks, and metrics endpoints are skipped.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        method = request.method
        path = request.url.path

        # Only audit write operations
        if method not in _WRITE_METHODS:
            return await call_next(request)

        # Skip paths that should not be audited
        if path in _SKIP_PATHS:
            return await call_next(request)
        for prefix in _SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Process the request first
        response = await call_next(request)

        # Only log successful writes (2xx and 3xx status codes)
        if response.status_code < 400:
            try:
                user_id, username = _extract_user_from_token(request)
                ip_address = _extract_client_ip(request)
                action, resource_type, resource_id = _classify_request(method, path)

                details = f"{method} {path} -> {response.status_code}"

                container = _get_audit_container()
                if container.db.is_available:
                    await container.audit_repo.log(
                        user_id=user_id,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        details=details,
                        username=username,
                        ip_address=ip_address,
                    )
            except Exception:
                # Never let audit logging break the request
                logger.debug("Audit logging failed", exc_info=True)

        return response
