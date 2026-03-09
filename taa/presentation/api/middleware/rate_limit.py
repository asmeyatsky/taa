"""Token-bucket rate limiter middleware for TAA API.

In-memory implementation with configurable rates per endpoint group.
No external dependencies (no Redis).
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp


@dataclass
class TokenBucket:
    """Token bucket for a single client key."""

    capacity: float
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_refill = time.monotonic()

    def consume(self) -> tuple[bool, float, float]:
        """Try to consume one token.

        Returns (allowed, remaining, reset_seconds).
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            remaining = self.tokens
            reset_after = (self.capacity - self.tokens) / self.refill_rate if self.refill_rate > 0 else 0
            return True, remaining, reset_after
        else:
            # Time until 1 token is available
            wait = (1.0 - self.tokens) / self.refill_rate if self.refill_rate > 0 else 60
            return False, 0.0, wait


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit group."""

    requests_per_minute: int
    name: str = ""

    @property
    def capacity(self) -> float:
        return float(self.requests_per_minute)

    @property
    def refill_rate(self) -> float:
        """Tokens per second."""
        return self.requests_per_minute / 60.0


# Default endpoint group configurations
DEFAULT_RATE_LIMITS: dict[str, RateLimitConfig] = {
    "auth": RateLimitConfig(requests_per_minute=5, name="auth"),
    "generate": RateLimitConfig(requests_per_minute=10, name="generate"),
    "read": RateLimitConfig(requests_per_minute=60, name="read"),
}

# Path prefix -> group mapping
DEFAULT_PATH_GROUPS: dict[str, str] = {
    "/api/auth/token": "auth",
    "/api/bigquery/export": "generate",
    "/api/domain/ldm": "generate",
    "/api/mock/generate": "generate",
    "/api/analytics/generate": "generate",
    "/api/compliance/report": "generate",
}


def _classify_endpoint(path: str, path_groups: dict[str, str]) -> str:
    """Map a request path to its rate-limit group."""
    for prefix, group in path_groups.items():
        if path.startswith(prefix):
            return group
    return "read"


def _client_key(request: Request) -> str:
    """Extract client identifier from request.

    Uses authenticated user if available (set by auth middleware),
    otherwise falls back to client IP.
    """
    # Check if user was set by auth dependency
    user = getattr(request.state, "user_id", None) if hasattr(request, "state") else None
    if user:
        return f"user:{user}"

    # Fall back to client IP
    client = request.client
    if client:
        return f"ip:{client.host}"
    # X-Forwarded-For header for proxied requests
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"ip:{forwarded.split(',')[0].strip()}"
    return "ip:unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm."""

    def __init__(
        self,
        app: ASGIApp,
        rate_limits: dict[str, RateLimitConfig] | None = None,
        path_groups: dict[str, str] | None = None,
        enabled: bool = True,
    ) -> None:
        super().__init__(app)
        self.rate_limits = rate_limits or DEFAULT_RATE_LIMITS
        self.path_groups = path_groups or DEFAULT_PATH_GROUPS
        self.enabled = enabled
        # buckets keyed by (client_key, group)
        self._buckets: dict[tuple[str, str], TokenBucket] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300  # clean up stale buckets every 5 minutes

    def _get_bucket(self, client: str, group: str) -> TokenBucket:
        key = (client, group)
        with self._lock:
            # Periodic cleanup of old buckets
            now = time.monotonic()
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_stale_buckets(now)
                self._last_cleanup = now

            if key not in self._buckets:
                config = self.rate_limits.get(group, self.rate_limits["read"])
                self._buckets[key] = TokenBucket(
                    capacity=config.capacity,
                    refill_rate=config.refill_rate,
                )
            return self._buckets[key]

    def _cleanup_stale_buckets(self, now: float) -> None:
        """Remove buckets that haven't been used in over 10 minutes."""
        stale_keys = [
            key for key, bucket in self._buckets.items()
            if now - bucket.last_refill > 600
        ]
        for key in stale_keys:
            del self._buckets[key]

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not self.enabled:
            return await call_next(request)

        path = request.url.path

        # Skip rate limiting for health/metrics endpoints
        if path in ("/api/health", "/metrics"):
            return await call_next(request)

        group = _classify_endpoint(path, self.path_groups)
        client = _client_key(request)
        bucket = self._get_bucket(client, group)

        config = self.rate_limits.get(group, self.rate_limits["read"])
        allowed, remaining, reset_after = bucket.consume()

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please retry later.",
                    "retry_after_seconds": round(reset_after, 1),
                },
                headers={
                    "X-RateLimit-Limit": str(config.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(round(reset_after, 1)),
                    "Retry-After": str(int(reset_after) + 1),
                },
            )

        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit"] = str(config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(int(remaining))
        response.headers["X-RateLimit-Reset"] = str(round(reset_after, 1))

        return response
