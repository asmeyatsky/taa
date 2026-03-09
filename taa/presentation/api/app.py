"""TAA FastAPI application."""

from __future__ import annotations

import logging
import os
import time
import resource
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from taa import __version__
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.routers import auth, bss, domain, bigquery, compliance, analytics, mock, users, audit, organizations
from taa.presentation.api.middleware.rate_limit import RateLimitMiddleware
from taa.presentation.api.middleware.metrics import MetricsMiddleware, metrics_endpoint, metrics_state
from taa.presentation.api.middleware.logging import RequestLoggingMiddleware
from taa.presentation.api.middleware.audit import AuditMiddleware
from taa.presentation.api.middleware.tenant import TenantMiddleware

logger = logging.getLogger(__name__)

# Track application start time at module level
_start_time: float = time.time()
_request_counter: dict[str, int] = {"total": 0}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown.

    On startup: initialise the SQLite database, seed the default
    organization, and seed demo users.
    On shutdown: close the database connection gracefully.
    """
    container = get_container()

    # Initialise database (creates tables on first run)
    try:
        await container.db.initialize()
        if container.db.is_available:
            logger.info("Database ready at %s", container.db.db_path)
            from taa.presentation.api.auth import DEMO_USERS_ENABLED
            if DEMO_USERS_ENABLED:
                await _seed_default_org(container)
                await _seed_demo_users(container)
            else:
                logger.info("Demo user seeding skipped (production mode)")
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


async def _seed_default_org(container) -> None:
    """Seed the default 'Demo' organization if it doesn't exist yet."""
    from taa.presentation.api.auth import DEFAULT_ORG_ID, DEFAULT_ORG_NAME, DEFAULT_ORG_SLUG

    existing = await container.org_repo.get_by_id(DEFAULT_ORG_ID)
    if existing is None:
        await container.org_repo.create({
            "id": DEFAULT_ORG_ID,
            "name": DEFAULT_ORG_NAME,
            "slug": DEFAULT_ORG_SLUG,
            "plan": "enterprise",
            "max_users": 100,
            "is_active": True,
        })
        logger.info("Seeded default organization: %s", DEFAULT_ORG_NAME)


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
            "https://*.run.app",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Audit logging (write operations)
    app.add_middleware(AuditMiddleware)

    # Tenant resolution
    from taa.presentation.api.auth import SECRET_KEY, ALGORITHM
    app.add_middleware(TenantMiddleware, secret_key=SECRET_KEY, algorithm=ALGORITHM)

    # Rate limiting
    rate_limit_enabled = os.getenv("TAA_RATE_LIMIT_ENABLED", "true").lower() != "false"
    app.add_middleware(RateLimitMiddleware, enabled=rate_limit_enabled)

    # Prometheus metrics
    app.add_middleware(MetricsMiddleware, state=metrics_state)

    # --- Routes ---

    # Prometheus metrics endpoint (auth-protected)
    from taa.presentation.api.auth import get_current_user
    from typing import Annotated
    from taa.presentation.api.auth import UserRecord

    @app.get("/metrics", tags=["Monitoring"])
    async def protected_metrics(
        user: Annotated[UserRecord, Depends(get_current_user)],
    ):
        from taa.presentation.api.auth import ROLES
        if "settings:manage" not in ROLES.get(user.role, []):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Admin access required")
        return await metrics_endpoint(None)

    # Health check: public liveness probe returns minimal info, detailed info requires auth
    @app.get("/api/health", tags=["Monitoring"])
    def health(request: Request) -> dict:
        _request_counter["total"] += 1
        result: dict = {"status": "ok", "version": __version__}

        # Only expose detailed info to authenticated admin users
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from taa.presentation.api.auth import SECRET_KEY, ALGORITHM, ROLES
                from jose import jwt
                payload = jwt.decode(auth_header[7:], SECRET_KEY, algorithms=[ALGORITHM])
                role = payload.get("role", "")
                if "settings:manage" in ROLES.get(role, []):
                    container = get_container()
                    try:
                        rusage = resource.getrusage(resource.RUSAGE_SELF)
                        memory_mb = round(rusage.ru_maxrss / (1024 * 1024), 2)
                        if memory_mb < 1:
                            memory_mb = round(rusage.ru_maxrss / 1024, 2)
                    except Exception:
                        memory_mb = None
                    result.update({
                        "database": "connected" if container.db.is_available else "unavailable",
                        "uptime_seconds": round(time.time() - _start_time, 1),
                        "requests_served": _request_counter["total"],
                        "memory_mb": memory_mb,
                    })
            except Exception:
                pass

        return result

    # Mount routers
    app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
    app.include_router(organizations.router, prefix="/api/orgs", tags=["Organizations"])
    app.include_router(bss.router, prefix="/api/bss", tags=["BSS"])
    app.include_router(domain.router, prefix="/api/domain", tags=["Domain"])
    app.include_router(bigquery.router, prefix="/api/bigquery", tags=["BigQuery Export"])
    app.include_router(compliance.router, prefix="/api/compliance", tags=["Compliance"])
    app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
    app.include_router(mock.router, prefix="/api/mock", tags=["Mock Data"])
    app.include_router(users.router, prefix="/api/users", tags=["Users"])
    app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])

    # Serve React static build if available
    frontend_dist = Path(__file__).parent.parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        # Serve static assets (JS, CSS, images) directly
        assets_dir = frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        index_html = frontend_dist / "index.html"

        # SPA catch-all: serve index.html for any non-API route
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str):
            # Serve actual static files if they exist (favicon, etc.)
            static_file = frontend_dist / path
            if path and static_file.exists() and static_file.is_file():
                return FileResponse(str(static_file))
            # Otherwise return index.html for client-side routing
            return FileResponse(str(index_html))

    return app


app = create_app()
