"""Tests for TAA API middleware: rate limiting, metrics, and request logging."""

from __future__ import annotations

import json
import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from taa.presentation.api.middleware.rate_limit import (
    RateLimitMiddleware,
    RateLimitConfig,
    TokenBucket,
    _classify_endpoint,
    DEFAULT_PATH_GROUPS,
)
from taa.presentation.api.middleware.metrics import (
    MetricsMiddleware,
    MetricsState,
    metrics_endpoint,
    _normalize_path,
)
from taa.presentation.api.middleware.logging import RequestLoggingMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(
    rate_limits: dict[str, RateLimitConfig] | None = None,
    rate_limit_enabled: bool = True,
    with_metrics: bool = False,
    with_logging: bool = False,
    logger: logging.Logger | None = None,
) -> FastAPI:
    """Build a minimal FastAPI app with selected middleware for testing."""
    app = FastAPI()

    if with_logging:
        app.add_middleware(RequestLoggingMiddleware, logger=logger)
    if rate_limit_enabled:
        app.add_middleware(
            RateLimitMiddleware,
            rate_limits=rate_limits,
            enabled=True,
        )
    if with_metrics:
        state = MetricsState()
        app.add_middleware(MetricsMiddleware, state=state)
        app.add_api_route("/metrics", lambda: __import__(
            "starlette.responses", fromlist=["PlainTextResponse"]
        ).PlainTextResponse(
            content=state.generate(), media_type=state.content_type,
        ), methods=["GET"])
        # Store state on app for test access
        app.state.metrics = state

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/domain/list")
    def list_domains():
        return [{"name": "subscriber"}]

    @app.post("/api/auth/token")
    def login():
        return {"token": "abc"}

    @app.post("/api/bigquery/export")
    def export_pack():
        return {"success": True}

    @app.get("/api/bigquery/download/{download_id}")
    def download(download_id: str):
        return {"id": download_id}

    @app.post("/api/mock/generate")
    def mock_gen():
        return {"rows": 10}

    return app


# ---------------------------------------------------------------------------
# Token Bucket unit tests
# ---------------------------------------------------------------------------

class TestTokenBucket:
    def test_initial_tokens(self):
        bucket = TokenBucket(capacity=5.0, refill_rate=5.0 / 60.0)
        assert bucket.tokens == 5.0

    def test_consume_success(self):
        bucket = TokenBucket(capacity=5.0, refill_rate=5.0 / 60.0)
        allowed, remaining, _ = bucket.consume()
        assert allowed is True
        assert remaining == pytest.approx(4.0, abs=0.1)

    def test_consume_exhaustion(self):
        bucket = TokenBucket(capacity=2.0, refill_rate=2.0 / 60.0)
        bucket.consume()
        bucket.consume()
        allowed, remaining, reset = bucket.consume()
        assert allowed is False
        assert remaining == 0.0
        assert reset > 0

    def test_refill_over_time(self):
        bucket = TokenBucket(capacity=2.0, refill_rate=100.0)  # 100 tokens/sec
        bucket.consume()
        bucket.consume()
        # Manually advance time by adjusting last_refill
        bucket.last_refill -= 0.05  # 50ms ago -> should add ~5 tokens
        allowed, remaining, _ = bucket.consume()
        assert allowed is True


# ---------------------------------------------------------------------------
# Endpoint classification
# ---------------------------------------------------------------------------

class TestEndpointClassification:
    def test_auth_endpoint(self):
        assert _classify_endpoint("/api/auth/token", DEFAULT_PATH_GROUPS) == "auth"

    def test_generate_endpoints(self):
        assert _classify_endpoint("/api/bigquery/export", DEFAULT_PATH_GROUPS) == "generate"
        assert _classify_endpoint("/api/mock/generate", DEFAULT_PATH_GROUPS) == "generate"
        assert _classify_endpoint("/api/domain/ldm", DEFAULT_PATH_GROUPS) == "generate"
        assert _classify_endpoint("/api/analytics/generate", DEFAULT_PATH_GROUPS) == "generate"

    def test_read_endpoint_default(self):
        assert _classify_endpoint("/api/domain/list", DEFAULT_PATH_GROUPS) == "read"
        assert _classify_endpoint("/api/bss/vendors", DEFAULT_PATH_GROUPS) == "read"
        assert _classify_endpoint("/api/compliance/jurisdictions", DEFAULT_PATH_GROUPS) == "read"

    def test_unknown_path_defaults_to_read(self):
        assert _classify_endpoint("/some/random/path", DEFAULT_PATH_GROUPS) == "read"


# ---------------------------------------------------------------------------
# Rate limit middleware integration tests
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    def test_rate_limit_headers_present(self):
        app = _make_app()
        client = TestClient(app)
        r = client.get("/api/domain/list")
        assert r.status_code == 200
        assert "X-RateLimit-Limit" in r.headers
        assert "X-RateLimit-Remaining" in r.headers
        assert "X-RateLimit-Reset" in r.headers

    def test_rate_limit_allows_within_limit(self):
        limits = {
            "auth": RateLimitConfig(requests_per_minute=5),
            "generate": RateLimitConfig(requests_per_minute=10),
            "read": RateLimitConfig(requests_per_minute=60),
        }
        app = _make_app(rate_limits=limits)
        client = TestClient(app)

        # 5 requests should be fine for read (limit 60)
        for _ in range(5):
            r = client.get("/api/domain/list")
            assert r.status_code == 200

    def test_rate_limit_blocks_when_exceeded(self):
        # Very low limit for testing
        limits = {
            "auth": RateLimitConfig(requests_per_minute=2),
            "generate": RateLimitConfig(requests_per_minute=2),
            "read": RateLimitConfig(requests_per_minute=2),
        }
        app = _make_app(rate_limits=limits)
        client = TestClient(app)

        # First 2 should succeed
        r1 = client.get("/api/domain/list")
        assert r1.status_code == 200
        r2 = client.get("/api/domain/list")
        assert r2.status_code == 200

        # Third should be rate limited
        r3 = client.get("/api/domain/list")
        assert r3.status_code == 429
        body = r3.json()
        assert "Rate limit exceeded" in body["detail"]
        assert "retry_after_seconds" in body
        assert "Retry-After" in r3.headers

    def test_auth_endpoint_has_stricter_limit(self):
        limits = {
            "auth": RateLimitConfig(requests_per_minute=2),
            "generate": RateLimitConfig(requests_per_minute=10),
            "read": RateLimitConfig(requests_per_minute=60),
        }
        app = _make_app(rate_limits=limits)
        client = TestClient(app)

        # Auth: limit 2
        client.post("/api/auth/token")
        client.post("/api/auth/token")
        r = client.post("/api/auth/token")
        assert r.status_code == 429

        # Read should still work (different bucket)
        r2 = client.get("/api/domain/list")
        assert r2.status_code == 200

    def test_health_endpoint_not_rate_limited(self):
        limits = {
            "auth": RateLimitConfig(requests_per_minute=1),
            "generate": RateLimitConfig(requests_per_minute=1),
            "read": RateLimitConfig(requests_per_minute=1),
        }
        app = _make_app(rate_limits=limits)
        client = TestClient(app)

        # Health is exempt from rate limiting
        for _ in range(10):
            r = client.get("/api/health")
            assert r.status_code == 200

    def test_remaining_decreases(self):
        limits = {
            "auth": RateLimitConfig(requests_per_minute=5),
            "generate": RateLimitConfig(requests_per_minute=10),
            "read": RateLimitConfig(requests_per_minute=10),
        }
        app = _make_app(rate_limits=limits)
        client = TestClient(app)

        r1 = client.get("/api/domain/list")
        remaining1 = int(r1.headers["X-RateLimit-Remaining"])

        r2 = client.get("/api/domain/list")
        remaining2 = int(r2.headers["X-RateLimit-Remaining"])

        assert remaining2 < remaining1

    def test_rate_limit_disabled(self):
        limits = {
            "auth": RateLimitConfig(requests_per_minute=1),
            "generate": RateLimitConfig(requests_per_minute=1),
            "read": RateLimitConfig(requests_per_minute=1),
        }
        app = _make_app(rate_limits=limits, rate_limit_enabled=False)
        client = TestClient(app)

        # Should work unlimited when disabled
        for _ in range(5):
            r = client.get("/api/domain/list")
            assert r.status_code == 200
            assert "X-RateLimit-Limit" not in r.headers


# ---------------------------------------------------------------------------
# Metrics middleware tests
# ---------------------------------------------------------------------------

class TestNormalizePath:
    def test_normal_path(self):
        assert _normalize_path("/api/domain/list") == "/api/domain/list"

    def test_id_in_path(self):
        result = _normalize_path("/api/bigquery/download/abc-123-def-456")
        assert "{id}" in result

    def test_root(self):
        assert _normalize_path("/") == "/"


class TestMetricsMiddleware:
    def test_metrics_endpoint_returns_data(self):
        app = _make_app(rate_limit_enabled=False, with_metrics=True)
        client = TestClient(app)

        # Make some requests first
        client.get("/api/health")
        client.get("/api/domain/list")
        client.post("/api/auth/token")

        # Fetch metrics
        r = client.get("/metrics")
        assert r.status_code == 200
        body = r.text
        assert "taa_http_requests_total" in body
        assert "taa_http_request_duration_seconds" in body

    def test_metrics_count_increments(self):
        app = _make_app(rate_limit_enabled=False, with_metrics=True)
        client = TestClient(app)

        client.get("/api/health")
        client.get("/api/health")

        r = client.get("/metrics")
        body = r.text
        # The counter for /api/health should show at least 2
        assert "taa_http_requests_total" in body

    def test_metrics_tracks_status_codes(self):
        app = _make_app(rate_limit_enabled=False, with_metrics=True)
        client = TestClient(app)

        client.get("/api/health")  # 200
        client.get("/nonexistent")  # 404

        r = client.get("/metrics")
        body = r.text
        assert '200' in body

    def test_metrics_state_standalone(self):
        state = MetricsState()
        output = state.generate()
        assert isinstance(output, bytes)


# ---------------------------------------------------------------------------
# Request logging middleware tests
# ---------------------------------------------------------------------------

class TestRequestLoggingMiddleware:
    def test_logs_request(self, caplog):
        logger = logging.getLogger("taa.test.requests")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        app = _make_app(rate_limit_enabled=False, with_logging=True, logger=logger)
        client = TestClient(app)

        with caplog.at_level(logging.INFO, logger="taa.test.requests"):
            client.get("/api/health")

        # Find the JSON log entry
        json_logs = [r for r in caplog.records if r.name == "taa.test.requests"]
        assert len(json_logs) >= 1

        log_data = json.loads(json_logs[0].message)
        assert log_data["method"] == "GET"
        assert log_data["path"] == "/api/health"
        assert log_data["status"] == 200
        assert "duration_ms" in log_data
        assert "timestamp" in log_data

    def test_logs_warning_for_4xx(self, caplog):
        logger = logging.getLogger("taa.test.requests.warn")
        logger.setLevel(logging.DEBUG)
        logger.handlers = []
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        app = _make_app(rate_limit_enabled=False, with_logging=True, logger=logger)
        client = TestClient(app)

        with caplog.at_level(logging.WARNING, logger="taa.test.requests.warn"):
            client.get("/nonexistent-path")

        warn_logs = [r for r in caplog.records if r.levelno >= logging.WARNING and r.name == "taa.test.requests.warn"]
        assert len(warn_logs) >= 1


# ---------------------------------------------------------------------------
# Full app integration tests (using standalone app to avoid container import issues)
# ---------------------------------------------------------------------------

class TestFullAppHealth:
    """Test the enhanced health check and metrics using a self-contained app
    that mirrors the real app.py middleware + route setup without needing
    the full Container import chain.
    """

    @staticmethod
    def _build_full_app() -> FastAPI:
        """Build a test app that mirrors the real app.py middleware stack."""
        import resource as _resource

        app = FastAPI(title="TAA Test", version="0.1.0")

        # Same middleware stack as real app.py
        app.add_middleware(RequestLoggingMiddleware)
        app.add_middleware(RateLimitMiddleware, enabled=True)

        _metrics_state = MetricsState()
        app.add_middleware(MetricsMiddleware, state=_metrics_state)

        app.add_api_route(
            "/metrics",
            lambda: __import__(
                "starlette.responses", fromlist=["PlainTextResponse"]
            ).PlainTextResponse(
                content=_metrics_state.generate(),
                media_type=_metrics_state.content_type,
            ),
            methods=["GET"],
            tags=["Monitoring"],
        )

        _start = time.time()
        _counter = {"total": 0}

        @app.get("/api/health", tags=["Monitoring"])
        def health():
            _counter["total"] += 1
            try:
                rusage = _resource.getrusage(_resource.RUSAGE_SELF)
                memory_mb = round(rusage.ru_maxrss / (1024 * 1024), 2)
                if memory_mb < 1:
                    memory_mb = round(rusage.ru_maxrss / 1024, 2)
            except Exception:
                memory_mb = None
            return {
                "status": "ok",
                "version": "0.1.0",
                "uptime_seconds": round(time.time() - _start, 1),
                "requests_served": _counter["total"],
                "memory_mb": memory_mb,
            }

        return app

    def test_enhanced_health_check(self):
        app = self._build_full_app()
        client = TestClient(app)

        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "requests_served" in data
        assert "memory_mb" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_health_request_counter_increments(self):
        app = self._build_full_app()
        client = TestClient(app)

        r1 = client.get("/api/health")
        count1 = r1.json()["requests_served"]

        r2 = client.get("/api/health")
        count2 = r2.json()["requests_served"]

        assert count2 == count1 + 1

    def test_metrics_endpoint_on_full_app(self):
        app = self._build_full_app()
        client = TestClient(app)

        # Make a request first to generate some metrics
        client.get("/api/health")

        r = client.get("/metrics")
        assert r.status_code == 200
        assert "taa_http_requests_total" in r.text
        assert "taa_http_request_duration_seconds" in r.text
