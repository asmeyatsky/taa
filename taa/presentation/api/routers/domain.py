"""Domain model endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taa.infrastructure.config.container import Container
from taa.domain.value_objects.enums import TelcoDomain
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import (
    ColumnDetail,
    TableDetail,
    DomainDetail,
    LDMRequest,
    LDMResponse,
)

router = APIRouter()


@router.get("/list")
def list_domains(container: Container = Depends(get_container)) -> list[dict]:
    """List all available telco domains."""
    domains = container.list_domains.execute()
    return [d.model_dump() for d in domains]


@router.post("/ldm", response_model=LDMResponse)
def generate_ldm(
    req: LDMRequest,
    container: Container = Depends(get_container),
) -> LDMResponse:
    """Generate full LDM with table and column detail for selected domains."""
    result_domains: list[DomainDetail] = []

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

        table_details = [
            TableDetail(
                name=t.name,
                telco_domain=t.telco_domain.value,
                column_count=len(t.columns),
                columns=[
                    ColumnDetail(
                        name=c.name,
                        bigquery_type=c.bigquery_type.value,
                        description=c.description,
                        nullable=c.nullable,
                        pii_category=c.pii_category.value if c.pii_category else None,
                    )
                    for c in t.columns
                ],
            )
            for t in enriched
        ]

        result_domains.append(DomainDetail(
            name=domain.value,
            table_count=len(table_details),
            tables=table_details,
        ))

    return LDMResponse(domains=result_domains)
