"""Structured JSON request logging middleware for TAA API.

Logs each request with method, path, status, duration, client IP,
and user ID (if authenticated). Log level configurable via TAA_LOG_LEVEL.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


def _configure_logger() -> logging.Logger:
    """Create a logger with JSON formatting for request logs."""
    logger = logging.getLogger("taa.api.requests")

    # Avoid adding duplicate handlers if called multiple times
    if not logger.handlers:
        level_name = os.getenv("TAA_LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        logger.setLevel(level)

        handler = logging.StreamHandler()
        handler.setLevel(level)
        logger.addHandler(handler)

    logger.propagate = False
    return logger


_logger = _configure_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs structured JSON for every HTTP request."""

    def __init__(self, app: ASGIApp, logger: logging.Logger | None = None) -> None:
        super().__init__(app)
        self.logger = logger or _logger

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        method = request.method
        path = request.url.path

        # Extract client IP
        client_ip = None
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host

        # Process request
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "method": method,
                "path": path,
                "status": 500,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
                "error": str(exc),
            }
            self.logger.error(json.dumps(log_entry))
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code

        # Try to extract user_id from request state (set by auth dependencies)
        user_id = None
        if hasattr(request, "state"):
            user_id = getattr(request.state, "user_id", None)

        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "WARNING" if status_code >= 400 else "INFO",
            "method": method,
            "path": path,
            "status": status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
            "user_id": user_id,
        }

        if status_code >= 500:
            self.logger.error(json.dumps(log_entry))
        elif status_code >= 400:
            self.logger.warning(json.dumps(log_entry))
        else:
            self.logger.info(json.dumps(log_entry))

        return response
