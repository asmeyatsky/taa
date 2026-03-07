"""Dependency injection container (composition root)."""

from __future__ import annotations

from taa.domain.services.pii_detection import PIIDetectionService
from taa.domain.services.partitioning import PartitioningService
from taa.domain.services.compliance import ComplianceService
from taa.domain.services.mapping_resolution import MappingResolutionService
from taa.domain.services.schema_service import SchemaService
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer
from taa.infrastructure.output.filesystem_writer import FilesystemWriter
from taa.infrastructure.persistence.yaml_repository import (
    YAMLDomainModelRepository,
    YAMLComplianceRuleRepository,
)
from taa.infrastructure.generators.bigquery_ddl import BigQueryDDLGenerator
from taa.infrastructure.generators.terraform import TerraformGenerator
from taa.infrastructure.generators.dataflow import DataflowPipelineGenerator
from taa.infrastructure.generators.airflow_dag import AirflowDAGGenerator
from taa.infrastructure.generators.compliance_report import ComplianceReportGenerator
from taa.infrastructure.vendor_mappings.readers import VendorSchemaReader
from taa.application.commands.generate_ddl import GenerateDDLCommand
from taa.application.commands.generate_terraform import GenerateTerraformCommand
from taa.application.commands.generate_pipeline import GeneratePipelineCommand
from taa.application.commands.generate_dag import GenerateDAGCommand
from taa.application.commands.generate_compliance import GenerateComplianceReportCommand
from taa.application.commands.generate_full_pack import GenerateFullPackCommand
from taa.application.commands.map_vendor_schema import MapVendorSchemaCommand
from taa.application.queries.handlers import (
    ListDomainsQuery,
    GetDomainModelQuery,
    ListVendorsQuery,
    ListJurisdictionsQuery,
)


class Container:
    """DI composition root - wires all dependencies together."""

    def __init__(self, project_id: str = "telco-analytics") -> None:
        self._project_id = project_id

        # Domain services
        self.pii_service = PIIDetectionService()
        self.partitioning_service = PartitioningService()
        self.compliance_service = ComplianceService()
        self.mapping_service = MappingResolutionService()
        self.schema_service = SchemaService()

        # Infrastructure
        self.renderer = JinjaRenderer()
        self.output_writer = FilesystemWriter()
        self.domain_repo = YAMLDomainModelRepository()
        self.compliance_rule_repo = YAMLComplianceRuleRepository()
        self.vendor_repo = VendorSchemaReader()

        # Generators
        self.ddl_generator = BigQueryDDLGenerator(self.renderer, project_id)
        self.terraform_generator = TerraformGenerator(self.renderer, project_id)
        self.pipeline_generator = DataflowPipelineGenerator(self.renderer)
        self.dag_generator = AirflowDAGGenerator(self.renderer)
        self.compliance_generator = ComplianceReportGenerator()

    # Commands
    @property
    def generate_ddl(self) -> GenerateDDLCommand:
        return GenerateDDLCommand(
            self.domain_repo, self.ddl_generator, self.output_writer,
            self.pii_service, self.partitioning_service,
        )

    @property
    def generate_terraform(self) -> GenerateTerraformCommand:
        return GenerateTerraformCommand(
            self.domain_repo, self.terraform_generator, self.output_writer,
            self.pii_service, self.schema_service,
        )

    @property
    def generate_pipeline(self) -> GeneratePipelineCommand:
        return GeneratePipelineCommand(self.pipeline_generator, self.output_writer)

    @property
    def generate_dag(self) -> GenerateDAGCommand:
        return GenerateDAGCommand(self.dag_generator, self.output_writer)

    @property
    def generate_compliance(self) -> GenerateComplianceReportCommand:
        return GenerateComplianceReportCommand(
            self.domain_repo, self.compliance_rule_repo, self.compliance_generator,
            self.output_writer, self.pii_service, self.compliance_service, self.schema_service,
        )

    @property
    def generate_full_pack(self) -> GenerateFullPackCommand:
        return GenerateFullPackCommand(
            self.generate_ddl, self.generate_terraform, self.generate_pipeline,
            self.generate_dag, self.generate_compliance,
        )

    @property
    def map_vendor_schema(self) -> MapVendorSchemaCommand:
        return MapVendorSchemaCommand(
            self.domain_repo, self.vendor_repo, self.mapping_service,
        )

    # Queries
    @property
    def list_domains(self) -> ListDomainsQuery:
        return ListDomainsQuery(self.domain_repo)

    @property
    def get_domain_model(self) -> GetDomainModelQuery:
        return GetDomainModelQuery(self.domain_repo)

    @property
    def list_vendors(self) -> ListVendorsQuery:
        return ListVendorsQuery(self.vendor_repo)

    @property
    def list_jurisdictions(self) -> ListJurisdictionsQuery:
        return ListJurisdictionsQuery(self.compliance_rule_repo)
