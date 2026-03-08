"""Mock data generation endpoints."""

from __future__ import annotations

import io
import uuid
import zipfile

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from taa.infrastructure.config.container import Container
from taa.infrastructure.generators.mock_data import MockDataGenerator
from taa.domain.value_objects.enums import TelcoDomain
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import MockDataRequest

router = APIRouter()


@router.post("/generate")
def generate_mock_data(
    req: MockDataRequest,
    container: Container = Depends(get_container),
) -> StreamingResponse:
    """Generate synthetic BSS test data and return as a ZIP."""
    gen = MockDataGenerator(seed=req.seed)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for domain_name in req.domains:
            domain = TelcoDomain(domain_name)
            tables = container.domain_repo.load_tables(domain)
            enriched = tuple(
                type(t)(
                    name=t.name, telco_domain=t.telco_domain,
                    columns=container.pii_service.enrich_columns(t.columns),
                    partitioning=t.partitioning, clustering=t.clustering,
                    dataset_name=t.dataset_name,
                )
                for t in tables
            )
            data_files = gen.generate_all(enriched, row_count=req.rows, fmt=req.format)
            for filename, content in data_files.items():
                zf.writestr(f"{domain.value}/{filename}", content)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=mock_data_{uuid.uuid4().hex[:8]}.zip"},
    )
