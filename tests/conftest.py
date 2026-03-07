"""TAA test configuration and shared fixtures."""

import pytest

from taa.domain.value_objects.enums import TelcoDomain, BSSVendor, PIICategory, BigQueryType
from taa.domain.value_objects.types import (
    Jurisdiction,
    PartitioningStrategy,
    ClusteringStrategy,
    PolicyTag,
    DAGSchedule,
)
from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.domain.entities.vendor_mapping import VendorMapping
from taa.domain.entities.compliance_rule import ComplianceRule
from taa.domain.entities.pipeline import Pipeline
from taa.domain.entities.dag import DAG, DAGTask


@pytest.fixture
def sample_column() -> Column:
    return Column(
        name="subscriber_id",
        bigquery_type=BigQueryType.STRING,
        description="Unique subscriber identifier",
        nullable=False,
    )


@pytest.fixture
def sample_pii_column() -> Column:
    return Column(
        name="msisdn",
        bigquery_type=BigQueryType.STRING,
        description="Mobile subscriber ISDN number",
        nullable=False,
        pii_category=PIICategory.MSISDN,
        policy_tag="projects/telco/locations/global/taxonomies/pii/policyTags/msisdn",
        masking_pattern="HASH",
    )


@pytest.fixture
def sample_table(sample_column: Column, sample_pii_column: Column) -> Table:
    return Table(
        name="subscriber_profile",
        telco_domain=TelcoDomain.SUBSCRIBER,
        columns=(sample_column, sample_pii_column),
        partitioning=PartitioningStrategy(column_name="activation_date", partition_type="DAY"),
        clustering=ClusteringStrategy(column_names=("subscriber_id",)),
        dataset_name="subscriber_ds",
    )


@pytest.fixture
def sample_dataset(sample_table: Table) -> Dataset:
    return Dataset(
        name="subscriber_ds",
        telco_domain=TelcoDomain.SUBSCRIBER,
        tables=(sample_table,),
        jurisdiction=Jurisdiction(
            code="SA",
            name="Saudi Arabia",
            primary_framework="PDPL",
            gcp_region="me-central1",
            data_residency_required=True,
        ),
        gcp_region="me-central1",
        kms_key_required=True,
    )


@pytest.fixture
def sample_vendor_mapping() -> VendorMapping:
    return VendorMapping(
        vendor=BSSVendor.AMDOCS,
        vendor_table="CM_SUBSCRIBER",
        vendor_field="SUB_ID",
        canonical_table="subscriber_profile",
        canonical_field="subscriber_id",
        transformation="CAST(SUB_ID AS STRING)",
        confidence=0.95,
    )


@pytest.fixture
def sample_compliance_rule() -> ComplianceRule:
    return ComplianceRule(
        rule_id="SA-PDPL-001",
        jurisdiction="SA",
        framework="PDPL",
        applicable_pii_categories=(PIICategory.MSISDN, PIICategory.IMSI),
        data_residency_required=True,
        encryption_required=True,
        kms_rotation_days=30,
        retention_months=24,
    )


@pytest.fixture
def saudi_jurisdiction() -> Jurisdiction:
    return Jurisdiction(
        code="SA",
        name="Saudi Arabia",
        primary_framework="PDPL",
        gcp_region="me-central1",
        data_residency_required=True,
    )
