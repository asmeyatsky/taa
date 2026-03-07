"""Tests for DI container."""

from taa.infrastructure.config.container import Container
from taa.infrastructure.config.settings import Settings
from taa.application.commands.generate_ddl import GenerateDDLCommand
from taa.application.commands.generate_terraform import GenerateTerraformCommand
from taa.application.commands.generate_pipeline import GeneratePipelineCommand
from taa.application.commands.generate_dag import GenerateDAGCommand
from taa.application.commands.generate_compliance import GenerateComplianceReportCommand
from taa.application.commands.generate_full_pack import GenerateFullPackCommand
from taa.application.commands.map_vendor_schema import MapVendorSchemaCommand
from taa.application.queries.handlers import (
    ListDomainsQuery, GetDomainModelQuery, ListVendorsQuery, ListJurisdictionsQuery,
)


class TestContainer:
    def setup_method(self):
        self.container = Container()

    def test_domain_services(self):
        assert self.container.pii_service is not None
        assert self.container.partitioning_service is not None
        assert self.container.compliance_service is not None
        assert self.container.mapping_service is not None
        assert self.container.schema_service is not None

    def test_infrastructure(self):
        assert self.container.renderer is not None
        assert self.container.output_writer is not None
        assert self.container.domain_repo is not None
        assert self.container.compliance_rule_repo is not None
        assert self.container.vendor_repo is not None

    def test_generators(self):
        assert self.container.ddl_generator is not None
        assert self.container.terraform_generator is not None
        assert self.container.pipeline_generator is not None
        assert self.container.dag_generator is not None
        assert self.container.compliance_generator is not None

    def test_commands(self):
        assert isinstance(self.container.generate_ddl, GenerateDDLCommand)
        assert isinstance(self.container.generate_terraform, GenerateTerraformCommand)
        assert isinstance(self.container.generate_pipeline, GeneratePipelineCommand)
        assert isinstance(self.container.generate_dag, GenerateDAGCommand)
        assert isinstance(self.container.generate_compliance, GenerateComplianceReportCommand)
        assert isinstance(self.container.generate_full_pack, GenerateFullPackCommand)
        assert isinstance(self.container.map_vendor_schema, MapVendorSchemaCommand)

    def test_queries(self):
        assert isinstance(self.container.list_domains, ListDomainsQuery)
        assert isinstance(self.container.get_domain_model, GetDomainModelQuery)
        assert isinstance(self.container.list_vendors, ListVendorsQuery)
        assert isinstance(self.container.list_jurisdictions, ListJurisdictionsQuery)

    def test_custom_project_id(self):
        c = Container(project_id="my-project")
        assert c._project_id == "my-project"


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.project_id == "telco-analytics"
        assert s.default_jurisdiction == "SA"
        assert s.default_region == "me-central1"
        assert s.output_dir == "./output"
