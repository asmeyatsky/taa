"""TAA FastAPI application."""

from __future__ import annotations

import logging
import os
import time
import resource
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from taa import __version__
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.routers import auth, bss, domain, bigquery, compliance, analytics, mock
from taa.presentation.api.middleware.rate_limit import RateLimitMiddleware
from taa.presentation.api.middleware.metrics import MetricsMiddleware, metrics_endpoint, metrics_state
from taa.presentation.api.middleware.logging import RequestLoggingMiddleware

logger = logging.getLogger(__name__)

# Track application start time at module level
_start_time: float = time.time()
_request_counter: dict[str, int] = {"total": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown.

    On startup: initialise the SQLite database and seed demo users.
    On shutdown: close the database connection gracefully.
    """
    container = get_container()

    # Initialise database (creates tables on first run)
    try:
        await container.db.initialize()
        if container.db.is_available:
            logger.info("Database ready at %s", container.db.db_path)
            await _seed_demo_users(container)
        else:
            logger.warning("Database unavailable - using in-memory fallback")
    except Exception:
        logger.exception("Database initialisation failed - using in-memory fallback")

    yield

    # Shutdown: close database
    try:
        await container.db.close()
    except Exception:
        logger.exception("Error closing database")


async def _seed_demo_users(container) -> None:
    """Seed demo users into the database if they don't exist yet."""
    from taa.presentation.api.auth import DEMO_USERS

    for user_data in DEMO_USERS:
        existing = await container.user_repo.get_by_username(user_data["username"])
        if existing is None:
            await container.user_repo.create(user_data)
            logger.info("Seeded demo user: %s", user_data["username"])


def create_app() -> FastAPI:
    """Create and configure the TAA FastAPI application."""
    app = FastAPI(
        title="TAA - Telco Analytics Accelerator",
        version=__version__,
        description="Auto-generates production-ready BigQuery DDL, Terraform, Dataflow pipelines, "
                    "Airflow DAGs, and compliance reports from telco BSS/OSS configurations.",
        lifespan=lifespan,
    )

    # --- Middleware (order matters: last added = first executed) ---

    # CORS must be outermost
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8001",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8001",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Rate limiting
    rate_limit_enabled = os.getenv("TAA_RATE_LIMIT_ENABLED", "true").lower() != "false"
    app.add_middleware(RateLimitMiddleware, enabled=rate_limit_enabled)

    # Prometheus metrics
    app.add_middleware(MetricsMiddleware, state=metrics_state)

    # --- Routes ---

    # Prometheus metrics endpoint
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], tags=["Monitoring"])

    # Enhanced health check
    @app.get("/api/health", tags=["Monitoring"])
    def health() -> dict:
        _request_counter["total"] += 1
        container = get_container()

        # Memory usage (RSS in MB)
        try:
            rusage = resource.getrusage(resource.RUSAGE_SELF)
            memory_mb = round(rusage.ru_maxrss / (1024 * 1024), 2)
            if memory_mb < 1:
                memory_mb = round(rusage.ru_maxrss / 1024, 2)
        except Exception:
            memory_mb = None

        uptime_seconds = round(time.time() - _start_time, 1)

        return {
            "status": "ok",
            "version": __version__,
            "database": "connected" if container.db.is_available else "unavailable",
            "uptime_seconds": uptime_seconds,
            "requests_served": _request_counter["total"],
            "memory_mb": memory_mb,
        }

    # Mount routers
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(bss.router, prefix="/api/bss", tags=["BSS"])
    app.include_router(domain.router, prefix="/api/domain", tags=["Domain"])
    app.include_router(bigquery.router, prefix="/api/bigquery", tags=["BigQuery Export"])
    app.include_router(compliance.router, prefix="/api/compliance", tags=["Compliance"])
    app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
    app.include_router(mock.router, prefix="/api/mock", tags=["Mock Data"])

    # Serve React static build if available
    frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()
