"""Generate Compliance Report command."""

from __future__ import annotations

from taa.application.dtos.models import GenerationRequest, GenerationResult
from taa.domain.ports.generators import ComplianceReportGeneratorPort
from taa.domain.ports.repositories import DomainModelRepositoryPort, ComplianceRuleRepositoryPort
from taa.domain.ports.infrastructure import OutputWriterPort
from taa.domain.services.pii_detection import PIIDetectionService
from taa.domain.services.compliance import ComplianceService
from taa.domain.services.schema_service import SchemaService
from taa.domain.value_objects.enums import TelcoDomain
from taa.application.commands.generate_terraform import JURISDICTIONS


class GenerateComplianceReportCommand:
    """Load tables, PII scan, evaluate rules, generate report, write output."""

    def __init__(
        self,
        domain_repo: DomainModelRepositoryPort,
        compliance_rule_repo: ComplianceRuleRepositoryPort,
        compliance_generator: ComplianceReportGeneratorPort,
        output_writer: OutputWriterPort,
        pii_service: PIIDetectionService | None = None,
        compliance_service: ComplianceService | None = None,
        schema_service: SchemaService | None = None,
    ) -> None:
        self._domain_repo = domain_repo
        self._compliance_rule_repo = compliance_rule_repo
        self._compliance_generator = compliance_generator
        self._output_writer = output_writer
        self._pii_service = pii_service or PIIDetectionService()
        self._compliance_service = compliance_service or ComplianceService()
        self._schema_service = schema_service or SchemaService()

    def execute(self, request: GenerationRequest) -> GenerationResult:
        files_generated: list[str] = []
        errors: list[str] = []

        jurisdiction = JURISDICTIONS.get(request.jurisdiction)
        rules = self._compliance_rule_repo.load_rules(request.jurisdiction)

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

                report = self._compliance_service.evaluate(ds, rules)

                # Generate JSON report
                json_content = self._compliance_generator.generate_json(report)
                json_path = request.output_dir / "compliance" / f"{domain.value}_compliance.json"
                self._output_writer.write(json_path, json_content)
                files_generated.append(str(json_path))

                # Generate Markdown report
                md_content = self._compliance_generator.generate_markdown(report)
                md_path = request.output_dir / "compliance" / f"{domain.value}_compliance.md"
                self._output_writer.write(md_path, md_content)
                files_generated.append(str(md_path))
            except Exception as e:
                errors.append(f"Error generating compliance report for {domain_name}: {e}")

        return GenerationResult(
            success=len(errors) == 0,
            files_generated=files_generated,
            errors=errors,
            summary=f"Generated {len(files_generated)} compliance report file(s)",
        )
