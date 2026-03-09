"""Prometheus-compatible metrics middleware for TAA API.

Exposes a /metrics endpoint with request count, duration, errors,
and active request gauge.
"""

from __future__ import annotations

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.types import ASGIApp

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False


def _normalize_path(path: str) -> str:
    """Collapse path parameters into placeholders for metric labels.

    E.g. /api/bigquery/download/abc-123 -> /api/bigquery/download/{id}
    """
    parts = path.strip("/").split("/")
    normalized = []
    for part in parts:
        # Heuristic: if a path segment looks like a UUID or random ID, replace it
        if len(part) > 8 and any(c.isdigit() for c in part):
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/" + "/".join(normalized)


class MetricsState:
    """Container for Prometheus metric objects.

    Uses its own registry to avoid conflicts with the default global registry.
    """

    def __init__(self) -> None:
        if not _PROMETHEUS_AVAILABLE:
            self.registry = None
            self.request_count = None
            self.request_duration = None
            self.request_errors = None
            self.active_requests = None
            return

        self.registry = CollectorRegistry()

        self.request_count = Counter(
            "taa_http_requests_total",
            "Total number of HTTP requests",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )
        self.request_duration = Histogram(
            "taa_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
            registry=self.registry,
        )
        self.request_errors = Counter(
            "taa_http_request_errors_total",
            "Total number of HTTP request errors (4xx and 5xx)",
            ["method", "endpoint", "status_code"],
            registry=self.registry,
        )
        self.active_requests = Gauge(
            "taa_http_active_requests",
            "Number of currently active HTTP requests",
            registry=self.registry,
        )

    def generate(self) -> bytes:
        if self.registry is None:
            return b"# prometheus_client not installed\n"
        return generate_latest(self.registry)

    @property
    def content_type(self) -> str:
        if not _PROMETHEUS_AVAILABLE:
            return "text/plain"
        return CONTENT_TYPE_LATEST


# Module-level singleton so it can be shared between middleware and route
metrics_state = MetricsState()


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that collects Prometheus metrics for all requests."""

    def __init__(self, app: ASGIApp, state: MetricsState | None = None) -> None:
        super().__init__(app)
        self.state = state or metrics_state

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip instrumenting the /metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        if self.state.registry is None:
            return await call_next(request)

        method = request.method
        endpoint = _normalize_path(request.url.path)

        self.state.active_requests.inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            self.state.active_requests.dec()
            self.state.request_errors.labels(
                method=method, endpoint=endpoint, status_code="500"
            ).inc()
            self.state.request_count.labels(
                method=method, endpoint=endpoint, status_code="500"
            ).inc()
            raise

        duration = time.perf_counter() - start
        status_code = str(response.status_code)

        self.state.request_count.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()
        self.state.request_duration.labels(
            method=method, endpoint=endpoint
        ).observe(duration)

        if response.status_code >= 400:
            self.state.request_errors.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()

        self.state.active_requests.dec()

        return response


def metrics_endpoint() -> PlainTextResponse:
    """Handler for GET /metrics endpoint."""
    return PlainTextResponse(
        content=metrics_state.generate(),
        media_type=metrics_state.content_type,
    )
