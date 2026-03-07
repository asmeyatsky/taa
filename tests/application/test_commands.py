"""Tests for application commands."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from taa.application.dtos.models import GenerationRequest
from taa.application.commands.generate_ddl import GenerateDDLCommand
from taa.application.commands.generate_terraform import GenerateTerraformCommand
from taa.application.commands.generate_pipeline import GeneratePipelineCommand
from taa.application.commands.generate_dag import GenerateDAGCommand
from taa.application.commands.generate_compliance import GenerateComplianceReportCommand
from taa.application.commands.generate_full_pack import GenerateFullPackCommand
from taa.application.commands.map_vendor_schema import MapVendorSchemaCommand
from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.entities.vendor_mapping import VendorMapping
from taa.domain.entities.compliance_rule import ComplianceRule
from taa.domain.value_objects.enums import TelcoDomain, BSSVendor, BigQueryType, PIICategory


@pytest.fixture
def mock_domain_repo():
    repo = MagicMock()
    col = Column(name="subscriber_id", bigquery_type=BigQueryType.STRING, nullable=False)
    table = Table(name="subscriber_profile", telco_domain=TelcoDomain.SUBSCRIBER,
                  columns=(col,), dataset_name="subscriber_ds")
    repo.load_tables.return_value = (table,)
    repo.list_domains.return_value = (TelcoDomain.SUBSCRIBER,)
    return repo


@pytest.fixture
def mock_output_writer():
    writer = MagicMock()
    writer.write_multiple.return_value = [Path("output/test.tf")]
    return writer


@pytest.fixture
def mock_ddl_generator():
    gen = MagicMock()
    gen.generate.return_value = "CREATE TABLE test (id STRING);"
    return gen


@pytest.fixture
def mock_terraform_generator():
    gen = MagicMock()
    gen.generate.return_value = {"main.tf": "terraform {}"}
    return gen


@pytest.fixture
def mock_pipeline_generator():
    gen = MagicMock()
    gen.generate.return_value = "# Pipeline code"
    return gen


@pytest.fixture
def mock_dag_generator():
    gen = MagicMock()
    gen.generate.return_value = "# DAG code"
    return gen


class TestGenerateDDLCommand:
    def test_generates_ddl(self, mock_domain_repo, mock_ddl_generator, mock_output_writer):
        cmd = GenerateDDLCommand(mock_domain_repo, mock_ddl_generator, mock_output_writer)
        request = GenerationRequest(domains=["subscriber"], output_dir=Path("/tmp/test"))
        result = cmd.execute(request)
        assert result.success
        assert len(result.files_generated) == 1
        mock_ddl_generator.generate.assert_called_once()

    def test_handles_invalid_domain(self, mock_domain_repo, mock_ddl_generator, mock_output_writer):
        cmd = GenerateDDLCommand(mock_domain_repo, mock_ddl_generator, mock_output_writer)
        request = GenerationRequest(domains=["nonexistent"], output_dir=Path("/tmp/test"))
        result = cmd.execute(request)
        assert not result.success
        assert len(result.errors) == 1


class TestGenerateTerraformCommand:
    def test_generates_terraform(self, mock_domain_repo, mock_terraform_generator, mock_output_writer):
        cmd = GenerateTerraformCommand(mock_domain_repo, mock_terraform_generator, mock_output_writer)
        request = GenerationRequest(domains=["subscriber"], jurisdiction="SA", output_dir=Path("/tmp/test"))
        result = cmd.execute(request)
        assert result.success
        mock_terraform_generator.generate.assert_called_once()


class TestGeneratePipelineCommand:
    def test_generates_pipelines(self, mock_pipeline_generator, mock_output_writer):
        cmd = GeneratePipelineCommand(mock_pipeline_generator, mock_output_writer)
        request = GenerationRequest(domains=["cdr_event"], output_dir=Path("/tmp/test"))
        result = cmd.execute(request)
        assert result.success
        assert len(result.files_generated) >= 1


class TestGenerateDAGCommand:
    def test_generates_dags(self, mock_dag_generator, mock_output_writer):
        cmd = GenerateDAGCommand(mock_dag_generator, mock_output_writer)
        request = GenerationRequest(domains=["cdr_event"], output_dir=Path("/tmp/test"))
        result = cmd.execute(request)
        assert result.success
        assert len(result.files_generated) >= 1


class TestGenerateComplianceReportCommand:
    def test_generates_report(self, mock_domain_repo, mock_output_writer):
        compliance_rule_repo = MagicMock()
        compliance_rule_repo.load_rules.return_value = ()
        compliance_gen = MagicMock()
        compliance_gen.generate_json.return_value = "{}"
        compliance_gen.generate_markdown.return_value = "# Report"

        cmd = GenerateComplianceReportCommand(
            mock_domain_repo, compliance_rule_repo, compliance_gen, mock_output_writer,
        )
        request = GenerationRequest(domains=["subscriber"], jurisdiction="SA", output_dir=Path("/tmp/test"))
        result = cmd.execute(request)
        assert result.success


class TestGenerateFullPackCommand:
    def test_generates_full_pack(self, mock_domain_repo, mock_ddl_generator,
                                  mock_terraform_generator, mock_pipeline_generator,
                                  mock_dag_generator, mock_output_writer):
        ddl_cmd = GenerateDDLCommand(mock_domain_repo, mock_ddl_generator, mock_output_writer)
        tf_cmd = GenerateTerraformCommand(mock_domain_repo, mock_terraform_generator, mock_output_writer)
        pipe_cmd = GeneratePipelineCommand(mock_pipeline_generator, mock_output_writer)
        dag_cmd = GenerateDAGCommand(mock_dag_generator, mock_output_writer)
        compliance_rule_repo = MagicMock()
        compliance_rule_repo.load_rules.return_value = ()
        compliance_gen = MagicMock()
        compliance_gen.generate_json.return_value = "{}"
        compliance_gen.generate_markdown.return_value = "# Report"
        comp_cmd = GenerateComplianceReportCommand(
            mock_domain_repo, compliance_rule_repo, compliance_gen, mock_output_writer,
        )

        cmd = GenerateFullPackCommand(ddl_cmd, tf_cmd, pipe_cmd, dag_cmd, comp_cmd)
        request = GenerationRequest(domains=["subscriber"], jurisdiction="SA", output_dir=Path("/tmp/test"))
        result = cmd.execute(request)
        assert result.success


class TestMapVendorSchemaCommand:
    def test_maps_vendor(self, mock_domain_repo):
        vendor_repo = MagicMock()
        vendor_repo.load_mappings.return_value = (
            VendorMapping(
                vendor=BSSVendor.AMDOCS, vendor_table="CM_SUB", vendor_field="SUB_ID",
                canonical_table="subscriber_profile", canonical_field="subscriber_id",
            ),
        )
        cmd = MapVendorSchemaCommand(mock_domain_repo, vendor_repo)
        result = cmd.execute("amdocs", "subscriber")
        assert result.vendor == "amdocs"
        assert result.domain == "subscriber"
        assert result.coverage_pct == 100.0
