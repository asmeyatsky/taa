"""Tests for domain entities."""

import pytest

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.domain.entities.vendor_mapping import VendorMapping
from taa.domain.entities.compliance_rule import ComplianceRule
from taa.domain.entities.pipeline import Pipeline
from taa.domain.entities.dag import DAG, DAGTask
from taa.domain.entities.analytics_template import AnalyticsTemplate
from taa.domain.value_objects.enums import (
    TelcoDomain, BSSVendor, PIICategory, BigQueryType,
    PipelineType, PipelineMode, TemplateType,
)
from taa.domain.value_objects.types import (
    Jurisdiction, PartitioningStrategy, ClusteringStrategy,
)


class TestColumn:
    def test_basic_column(self, sample_column):
        assert sample_column.name == "subscriber_id"
        assert sample_column.bigquery_type == BigQueryType.STRING
        assert not sample_column.is_pii

    def test_pii_column(self, sample_pii_column):
        assert sample_pii_column.is_pii
        assert sample_pii_column.pii_category == PIICategory.MSISDN

    def test_frozen(self, sample_column):
        with pytest.raises(AttributeError):
            sample_column.name = "other"


class TestTable:
    def test_basic_table(self, sample_table):
        assert sample_table.name == "subscriber_profile"
        assert sample_table.telco_domain == TelcoDomain.SUBSCRIBER
        assert len(sample_table.columns) == 2

    def test_add_column(self, sample_table):
        new_col = Column(name="status", bigquery_type=BigQueryType.STRING)
        new_table = sample_table.add_column(new_col)
        assert len(new_table.columns) == 3
        assert new_table.columns[-1].name == "status"
        # Original unchanged
        assert len(sample_table.columns) == 2

    def test_pii_columns(self, sample_table):
        pii = sample_table.pii_columns()
        assert len(pii) == 1
        assert pii[0].name == "msisdn"

    def test_has_pii(self, sample_table):
        assert sample_table.has_pii()

    def test_no_pii(self, sample_column):
        table = Table(
            name="test",
            telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(sample_column,),
        )
        assert not table.has_pii()


class TestDataset:
    def test_requires_encryption_kms(self, sample_dataset):
        assert sample_dataset.requires_encryption()

    def test_requires_encryption_residency(self, sample_table):
        ds = Dataset(
            name="test",
            telco_domain=TelcoDomain.SUBSCRIBER,
            tables=(sample_table,),
            jurisdiction=Jurisdiction(
                code="SA", name="Saudi Arabia", primary_framework="PDPL",
                gcp_region="me-central1", data_residency_required=True,
            ),
        )
        assert ds.requires_encryption()

    def test_requires_encryption_pii(self, sample_table):
        ds = Dataset(
            name="test",
            telco_domain=TelcoDomain.SUBSCRIBER,
            tables=(sample_table,),
        )
        assert ds.requires_encryption()

    def test_no_encryption_needed(self, sample_column):
        table = Table(name="test", telco_domain=TelcoDomain.SUBSCRIBER, columns=(sample_column,))
        ds = Dataset(name="test", telco_domain=TelcoDomain.SUBSCRIBER, tables=(table,))
        assert not ds.requires_encryption()


class TestVendorMapping:
    def test_basic(self, sample_vendor_mapping):
        assert sample_vendor_mapping.vendor == BSSVendor.AMDOCS
        assert sample_vendor_mapping.confidence == 0.95


class TestComplianceRule:
    def test_basic(self, sample_compliance_rule):
        assert sample_compliance_rule.rule_id == "SA-PDPL-001"
        assert sample_compliance_rule.kms_rotation_days == 30
        assert PIICategory.MSISDN in sample_compliance_rule.applicable_pii_categories


class TestPipeline:
    def test_basic(self):
        p = Pipeline(
            name="cdr_ingestion",
            pipeline_type=PipelineType.BATCH_INGESTION,
            source_vendor=BSSVendor.AMDOCS,
            target_tables=("cdr_event",),
            mode=PipelineMode.BATCH,
            telco_domain=TelcoDomain.CDR_EVENT,
        )
        assert p.name == "cdr_ingestion"
        assert p.mode == PipelineMode.BATCH


class TestDAG:
    def test_basic(self):
        tasks = (
            DAGTask(task_id="extract", operator="BigQueryOperator"),
            DAGTask(task_id="transform", operator="DataflowOperator", upstream_tasks=("extract",)),
        )
        dag = DAG(dag_id="daily_cdr", schedule="0 2 * * *", tasks=tasks)
        assert dag.dag_id == "daily_cdr"
        assert len(dag.task_ids()) == 2

    def test_get_task(self):
        task = DAGTask(task_id="extract", operator="BigQueryOperator")
        dag = DAG(dag_id="test", schedule="@daily", tasks=(task,))
        assert dag.get_task("extract") == task
        assert dag.get_task("nonexistent") is None


class TestAnalyticsTemplate:
    def test_basic(self):
        t = AnalyticsTemplate(
            name="churn_model",
            template_type=TemplateType.CHURN_PREDICTION,
            required_tables=("subscriber_profile", "cdr_event"),
            metrics=("monthly_churn_rate", "arpu"),
        )
        assert t.name == "churn_model"
        assert len(t.required_tables) == 2
