"""TAA FastAPI application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from taa import __version__
from taa.presentation.api.routers import auth, bss, domain, bigquery, compliance, analytics, mock


def create_app() -> FastAPI:
    """Create and configure the TAA FastAPI application."""
    app = FastAPI(
        title="TAA - Telco Analytics Accelerator",
        version=__version__,
        description="Auto-generates production-ready BigQuery DDL, Terraform, Dataflow pipelines, "
                    "Airflow DAGs, and compliance reports from telco BSS/OSS configurations.",
    )

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

    # Health check
    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "version": __version__}

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
