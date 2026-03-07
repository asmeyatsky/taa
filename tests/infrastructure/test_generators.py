"""Tests for infrastructure generators."""

import pytest
from pathlib import Path

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.domain.entities.pipeline import Pipeline
from taa.domain.entities.dag import DAG, DAGTask
from taa.domain.value_objects.enums import (
    TelcoDomain, BigQueryType, PIICategory, PipelineType, PipelineMode, BSSVendor,
)
from taa.domain.value_objects.types import (
    Jurisdiction, PartitioningStrategy, ClusteringStrategy,
)
from taa.domain.services.compliance import ComplianceReport, ComplianceFinding
from taa.infrastructure.generators.bigquery_ddl import BigQueryDDLGenerator
from taa.infrastructure.generators.terraform import TerraformGenerator
from taa.infrastructure.generators.dataflow import DataflowPipelineGenerator
from taa.infrastructure.generators.airflow_dag import AirflowDAGGenerator
from taa.infrastructure.generators.compliance_report import ComplianceReportGenerator
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer


@pytest.fixture
def renderer():
    return JinjaRenderer()


@pytest.fixture
def test_table():
    cols = (
        Column(name="subscriber_id", bigquery_type=BigQueryType.STRING, nullable=False,
               description="Unique subscriber ID"),
        Column(name="msisdn", bigquery_type=BigQueryType.STRING,
               pii_category=PIICategory.MSISDN,
               policy_tag="projects/telco/locations/global/taxonomies/pii/policyTags/msisdn"),
        Column(name="status", bigquery_type=BigQueryType.STRING),
        Column(name="activation_date", bigquery_type=BigQueryType.DATE, nullable=False),
    )
    return Table(
        name="subscriber_profile",
        telco_domain=TelcoDomain.SUBSCRIBER,
        columns=cols,
        partitioning=PartitioningStrategy(column_name="activation_date", partition_type="DAY"),
        clustering=ClusteringStrategy(column_names=("subscriber_id",)),
        dataset_name="subscriber_ds",
    )


@pytest.fixture
def test_dataset(test_table):
    return Dataset(
        name="subscriber_ds",
        telco_domain=TelcoDomain.SUBSCRIBER,
        tables=(test_table,),
        jurisdiction=Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                                 gcp_region="me-central1", data_residency_required=True),
        gcp_region="me-central1",
        kms_key_required=True,
    )


class TestBigQueryDDLGenerator:
    def test_generate_table(self, renderer, test_table):
        gen = BigQueryDDLGenerator(renderer)
        ddl = gen.generate_table(test_table)
        assert "CREATE TABLE" in ddl
        assert "subscriber_profile" in ddl
        assert "subscriber_id" in ddl
        assert "NOT NULL" in ddl
        assert "PARTITION BY" in ddl
        assert "CLUSTER BY" in ddl

    def test_generate_dataset(self, renderer, test_table):
        gen = BigQueryDDLGenerator(renderer)
        ddl = gen.generate((test_table,), "subscriber_ds")
        assert "subscriber_ds" in ddl
        assert "CREATE TABLE" in ddl

    def test_pii_policy_tag(self, renderer, test_table):
        gen = BigQueryDDLGenerator(renderer)
        ddl = gen.generate_table(test_table)
        assert "policy_tags" in ddl or "policyTags" in ddl


class TestTerraformGenerator:
    def test_generate(self, renderer, test_dataset):
        gen = TerraformGenerator(renderer)
        files = gen.generate((test_dataset,))
        assert "main.tf" in files
        assert "bigquery_dataset.tf" in files
        assert "kms.tf" in files
        assert "variables.tf" in files
        assert "iam.tf" in files
        assert "composer.tf" in files
        assert "monitoring.tf" in files
        assert "vertex_ai.tf" in files
        assert "audit_logging.tf" in files
        assert "dlp.tf" in files
        assert len(files) == 12

    def test_bigquery_dataset(self, renderer, test_dataset):
        gen = TerraformGenerator(renderer)
        files = gen.generate((test_dataset,))
        assert "subscriber_ds" in files["bigquery_dataset.tf"]
        assert "google_bigquery_dataset" in files["bigquery_dataset.tf"]

    def test_kms_config(self, renderer, test_dataset):
        gen = TerraformGenerator(renderer)
        files = gen.generate((test_dataset,))
        assert "google_kms" in files["kms.tf"]


class TestDataflowPipelineGenerator:
    def test_generate_batch(self, renderer):
        gen = DataflowPipelineGenerator(renderer)
        pipeline = Pipeline(
            name="subscriber_ingestion",
            pipeline_type=PipelineType.BATCH_INGESTION,
            mode=PipelineMode.BATCH,
            telco_domain=TelcoDomain.SUBSCRIBER,
        )
        code = gen.generate(pipeline)
        assert "apache_beam" in code
        assert "subscriber_ingestion" in code

    def test_generate_cdr_mediation(self, renderer):
        gen = DataflowPipelineGenerator(renderer)
        pipeline = Pipeline(
            name="cdr_mediation",
            pipeline_type=PipelineType.CDR_MEDIATION,
            telco_domain=TelcoDomain.CDR_EVENT,
        )
        code = gen.generate(pipeline)
        assert "PubSub" in code or "ReadFromPubSub" in code

    def test_invalid_type(self, renderer):
        gen = DataflowPipelineGenerator(renderer)
        # PipelineType is an enum, so we can't pass an invalid value easily
        # Instead test that all valid types work
        for pt in PipelineType:
            pipeline = Pipeline(name="test", pipeline_type=pt, telco_domain=TelcoDomain.CDR_EVENT)
            code = gen.generate(pipeline)
            assert "apache_beam" in code


class TestAirflowDAGGenerator:
    def test_generate(self, renderer):
        gen = AirflowDAGGenerator(renderer)
        dag = DAG(
            dag_id="daily_cdr",
            schedule="0 2 * * *",
            tasks=(
                DAGTask(task_id="extract", operator="BigQueryInsertJobOperator"),
                DAGTask(task_id="transform", operator="DataflowStartFlexTemplateOperator",
                       upstream_tasks=("extract",)),
            ),
            sla_seconds=7200,
            retries=3,
        )
        code = gen.generate(dag)
        assert "daily_cdr" in code
        assert "0 2 * * *" in code
        assert "extract" in code
        assert "transform" in code


class TestComplianceReportGenerator:
    def test_generate_json(self):
        gen = ComplianceReportGenerator()
        report = ComplianceReport(
            jurisdiction="SA",
            framework="PDPL",
            findings=(ComplianceFinding(
                rule_id="SA-001", severity="HIGH",
                description="Missing policy tag", remediation="Add tag",
            ),),
            pii_inventory={"subscriber_profile": ["msisdn"]},
            passed=False,
        )
        output = gen.generate_json(report)
        assert "SA" in output
        assert "PDPL" in output
        assert "SA-001" in output

    def test_generate_markdown(self):
        gen = ComplianceReportGenerator()
        report = ComplianceReport(
            jurisdiction="SA", framework="PDPL",
            findings=(), pii_inventory={}, passed=True,
        )
        output = gen.generate_markdown(report)
        assert "PASSED" in output
        assert "SA" in output

    def test_generate_retention_ddl(self, test_table):
        gen = ComplianceReportGenerator()
        from taa.domain.entities.compliance_rule import ComplianceRule
        rules = (ComplianceRule(
            rule_id="SA-001", jurisdiction="SA", framework="PDPL",
            applicable_pii_categories=(), data_residency_required=True,
            encryption_required=True, kms_rotation_days=90, retention_months=24,
        ),)
        ddl = gen.generate_retention_ddl((test_table,), rules)
        assert "DELETE FROM" in ddl
        assert "subscriber_profile" in ddl
        assert "24" in ddl
        assert "activation_date" in ddl


class TestAnalyticsTemplateGenerator:
    def test_generate_single(self, renderer):
        from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
        gen = AnalyticsTemplateGenerator(renderer)
        sql = gen.generate("churn_prediction")
        assert "churn" in sql.lower()
        assert "SELECT" in sql or "CREATE" in sql

    def test_generate_all(self, renderer):
        from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
        gen = AnalyticsTemplateGenerator(renderer)
        results = gen.generate_all()
        assert len(results) == 5
        assert "churn_prediction" in results
        assert "revenue_leakage" in results
        assert "arpu_analysis" in results
        assert "network_quality" in results
        assert "five_g_monetization" in results

    def test_list_templates(self, renderer):
        from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
        gen = AnalyticsTemplateGenerator(renderer)
        templates = gen.list_templates()
        assert len(templates) == 5

    def test_invalid_template(self, renderer):
        from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
        gen = AnalyticsTemplateGenerator(renderer)
        with pytest.raises(ValueError, match="Unknown analytics template"):
            gen.generate("nonexistent")


class TestAWSRedshiftDDLGenerator:
    def test_generate(self, renderer, test_table):
        from taa.infrastructure.generators.multicloud_ddl import AWSRedshiftDDLGenerator
        gen = AWSRedshiftDDLGenerator(renderer)
        ddl = gen.generate((test_table,), "subscriber_ds")
        assert "subscriber_profile" in ddl
        assert "subscriber_id" in ddl

    def test_generate_with_dataset(self, renderer, test_table):
        from taa.infrastructure.generators.multicloud_ddl import AWSRedshiftDDLGenerator
        gen = AWSRedshiftDDLGenerator(renderer)
        ddl = gen.generate((test_table,), "test_schema")
        assert "test_schema" in ddl


class TestAWSCloudFormationGenerator:
    def test_generate(self, renderer, test_dataset):
        from taa.infrastructure.generators.multicloud_ddl import AWSCloudFormationGenerator
        gen = AWSCloudFormationGenerator(renderer)
        files = gen.generate((test_dataset,))
        assert "cloudformation.yaml" in files
        content = files["cloudformation.yaml"]
        assert "AWSTemplateFormatVersion" in content or "AWS" in content

class TestAzureSynapseDDLGenerator:
    def test_generate(self, renderer, test_table):
        from taa.infrastructure.generators.multicloud_ddl import AzureSynapseDDLGenerator
        gen = AzureSynapseDDLGenerator(renderer)
        ddl = gen.generate((test_table,), "subscriber_ds")
        assert "subscriber_profile" in ddl
        assert "subscriber_id" in ddl


class TestAzureBicepGenerator:
    def test_generate(self, renderer, test_dataset):
        from taa.infrastructure.generators.multicloud_ddl import AzureBicepGenerator
        gen = AzureBicepGenerator(renderer)
        files = gen.generate((test_dataset,))
        assert "main.bicep" in files
        content = files["main.bicep"]
        assert "resource" in content.lower() or "param" in content.lower()
