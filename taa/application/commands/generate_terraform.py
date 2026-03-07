"""Generate Terraform command."""

from __future__ import annotations

from pathlib import Path

from taa.application.dtos.models import GenerationRequest, GenerationResult
from taa.domain.ports.generators import TerraformGeneratorPort
from taa.domain.ports.repositories import DomainModelRepositoryPort
from taa.domain.ports.infrastructure import OutputWriterPort
from taa.domain.services.pii_detection import PIIDetectionService
from taa.domain.services.schema_service import SchemaService
from taa.domain.value_objects.enums import TelcoDomain
from taa.domain.value_objects.types import Jurisdiction


JURISDICTIONS: dict[str, Jurisdiction] = {
    "SA": Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL", gcp_region="me-central1", data_residency_required=True),
    "AE": Jurisdiction(code="AE", name="UAE", primary_framework="PDPL", gcp_region="me-central1", data_residency_required=True),
    "KW": Jurisdiction(code="KW", name="Kuwait", primary_framework="CITRA", gcp_region="me-central1", data_residency_required=True),
    "EG": Jurisdiction(code="EG", name="Egypt", primary_framework="NTRA", gcp_region="me-central2", data_residency_required=True),
    "GB": Jurisdiction(code="GB", name="United Kingdom", primary_framework="GDPR_PECR", gcp_region="europe-west2", data_residency_required=False),
    "EU": Jurisdiction(code="EU", name="European Union", primary_framework="GDPR", gcp_region="europe-west1", data_residency_required=False),
    "IN": Jurisdiction(code="IN", name="India", primary_framework="DPDP", gcp_region="asia-south1", data_residency_required=True),
    "TR": Jurisdiction(code="TR", name="Turkey", primary_framework="KVKK", gcp_region="europe-west1", data_residency_required=True),
    "IE": Jurisdiction(code="IE", name="Ireland", primary_framework="GDPR_EPRIVACY", gcp_region="europe-west1", data_residency_required=False),
    "ZA": Jurisdiction(code="ZA", name="South Africa", primary_framework="POPIA", gcp_region="africa-south1", data_residency_required=True),
}


class GenerateTerraformCommand:
    """Load tables, build datasets, detect PII for KMS, generate Terraform, write output."""

    def __init__(
        self,
        domain_repo: DomainModelRepositoryPort,
        terraform_generator: TerraformGeneratorPort,
        output_writer: OutputWriterPort,
        pii_service: PIIDetectionService | None = None,
        schema_service: SchemaService | None = None,
    ) -> None:
        self._domain_repo = domain_repo
        self._terraform_generator = terraform_generator
        self._output_writer = output_writer
        self._pii_service = pii_service or PIIDetectionService()
        self._schema_service = schema_service or SchemaService()

    def execute(self, request: GenerationRequest) -> GenerationResult:
        files_generated: list[str] = []
        errors: list[str] = []

        jurisdiction = JURISDICTIONS.get(request.jurisdiction)
        datasets = []

        for domain_name in request.domains:
            try:
                domain = TelcoDomain(domain_name)
                tables = self._domain_repo.load_tables(domain)

                # Enrich PII
                enriched_tables = []
                for table in tables:
                    from taa.domain.entities.table import Table
                    enriched_cols = self._pii_service.enrich_columns(table.columns)
                    enriched_tables.append(Table(
                        name=table.name,
                        telco_domain=table.telco_domain,
                        columns=enriched_cols,
                        partitioning=table.partitioning,
                        clustering=table.clustering,
                        dataset_name=table.dataset_name,
                    ))

                ds = self._schema_service.build_dataset(
                    f"{domain.value}_ds", domain, tuple(enriched_tables),
                    jurisdiction=jurisdiction,
                    gcp_region=request.gcp_region or (jurisdiction.gcp_region if jurisdiction else ""),
                )
                datasets.append(ds)
            except Exception as e:
                errors.append(f"Error building dataset for {domain_name}: {e}")

        if datasets:
            try:
                tf_files = self._terraform_generator.generate(tuple(datasets))
                output_dir = request.output_dir / "terraform"
                written = self._output_writer.write_multiple(tf_files, output_dir)
                files_generated.extend(str(p) for p in written)
            except Exception as e:
                errors.append(f"Error generating Terraform: {e}")

        return GenerationResult(
            success=len(errors) == 0,
            files_generated=files_generated,
            errors=errors,
            summary=f"Generated {len(files_generated)} Terraform file(s)",
        )
