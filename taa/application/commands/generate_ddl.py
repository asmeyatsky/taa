"""Generate DDL command."""

from __future__ import annotations

from pathlib import Path

from taa.application.dtos.models import GenerationRequest, GenerationResult
from taa.domain.ports.generators import DDLGeneratorPort
from taa.domain.ports.repositories import DomainModelRepositoryPort
from taa.domain.ports.infrastructure import OutputWriterPort
from taa.domain.services.pii_detection import PIIDetectionService
from taa.domain.services.partitioning import PartitioningService
from taa.domain.value_objects.enums import TelcoDomain


class GenerateDDLCommand:
    """Load tables, PII scan, apply partitioning, generate DDL, write output."""

    def __init__(
        self,
        domain_repo: DomainModelRepositoryPort,
        ddl_generator: DDLGeneratorPort,
        output_writer: OutputWriterPort,
        pii_service: PIIDetectionService | None = None,
        partitioning_service: PartitioningService | None = None,
    ) -> None:
        self._domain_repo = domain_repo
        self._ddl_generator = ddl_generator
        self._output_writer = output_writer
        self._pii_service = pii_service or PIIDetectionService()
        self._partitioning_service = partitioning_service or PartitioningService()

    def execute(self, request: GenerationRequest) -> GenerationResult:
        files_generated: list[str] = []
        errors: list[str] = []

        for domain_name in request.domains:
            try:
                domain = TelcoDomain(domain_name)
                tables = self._domain_repo.load_tables(domain)

                # Enrich with PII and partitioning
                enriched_tables = []
                for table in tables:
                    from taa.domain.entities.table import Table
                    enriched_cols = self._pii_service.enrich_columns(table.columns)
                    enriched = Table(
                        name=table.name,
                        telco_domain=table.telco_domain,
                        columns=enriched_cols,
                        partitioning=table.partitioning,
                        clustering=table.clustering,
                        dataset_name=table.dataset_name,
                    )
                    enriched = self._partitioning_service.apply_all(enriched)
                    enriched_tables.append(enriched)

                dataset_name = f"{domain.value}_ds"
                ddl = self._ddl_generator.generate(tuple(enriched_tables), dataset_name)

                output_path = request.output_dir / "bigquery" / f"{domain.value}.sql"
                self._output_writer.write(output_path, ddl)
                files_generated.append(str(output_path))
            except Exception as e:
                errors.append(f"Error generating DDL for {domain_name}: {e}")

        return GenerationResult(
            success=len(errors) == 0,
            files_generated=files_generated,
            errors=errors,
            summary=f"Generated DDL for {len(files_generated)} domain(s)",
        )
