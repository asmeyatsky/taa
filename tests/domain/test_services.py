"""Tests for domain services."""

import pytest

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.domain.entities.vendor_mapping import VendorMapping
from taa.domain.entities.compliance_rule import ComplianceRule
from taa.domain.value_objects.enums import TelcoDomain, BSSVendor, PIICategory, BigQueryType
from taa.domain.value_objects.types import Jurisdiction, PartitioningStrategy, ClusteringStrategy
from taa.domain.services.pii_detection import PIIDetectionService
from taa.domain.services.partitioning import PartitioningService
from taa.domain.services.compliance import ComplianceService
from taa.domain.services.mapping_resolution import MappingResolutionService
from taa.domain.services.schema_service import SchemaService


class TestPIIDetectionService:
    def setup_method(self):
        self.service = PIIDetectionService()

    def test_detect_msisdn(self):
        assert self.service.classify_column("msisdn") == PIICategory.MSISDN
        assert self.service.classify_column("calling_number") == PIICategory.MSISDN

    def test_detect_imsi(self):
        assert self.service.classify_column("imsi") == PIICategory.IMSI

    def test_detect_imei(self):
        assert self.service.classify_column("imei") == PIICategory.IMEI
        assert self.service.classify_column("device_id") == PIICategory.IMEI

    def test_detect_email(self):
        assert self.service.classify_column("email") == PIICategory.EMAIL
        assert self.service.classify_column("e_mail_address") == PIICategory.EMAIL

    def test_detect_national_id(self):
        assert self.service.classify_column("national_id") == PIICategory.NATIONAL_ID

    def test_detect_name(self):
        assert self.service.classify_column("first_name") == PIICategory.NAME
        assert self.service.classify_column("customer_name") == PIICategory.NAME

    def test_detect_address(self):
        assert self.service.classify_column("address") == PIICategory.ADDRESS

    def test_detect_dob(self):
        assert self.service.classify_column("date_of_birth") == PIICategory.DATE_OF_BIRTH
        assert self.service.classify_column("dob") == PIICategory.DATE_OF_BIRTH

    def test_detect_ip(self):
        assert self.service.classify_column("ip_address") == PIICategory.IP_ADDRESS
        assert self.service.classify_column("source_ip") == PIICategory.IP_ADDRESS

    def test_detect_location(self):
        assert self.service.classify_column("latitude") == PIICategory.LOCATION
        assert self.service.classify_column("cell_id") == PIICategory.LOCATION

    def test_no_pii(self):
        assert self.service.classify_column("subscriber_id") is None
        assert self.service.classify_column("event_type") is None
        assert self.service.classify_column("amount") is None

    def test_scan_columns(self):
        cols = (
            Column(name="msisdn", bigquery_type=BigQueryType.STRING),
            Column(name="amount", bigquery_type=BigQueryType.FLOAT64),
            Column(name="email", bigquery_type=BigQueryType.STRING),
        )
        results = self.service.scan_columns(cols)
        assert len(results) == 2
        categories = [cat for _, cat in results]
        assert PIICategory.MSISDN in categories
        assert PIICategory.EMAIL in categories

    def test_enrich_column(self):
        col = Column(name="msisdn", bigquery_type=BigQueryType.STRING)
        enriched = self.service.enrich_column(col)
        assert enriched.pii_category == PIICategory.MSISDN
        assert enriched.policy_tag is not None
        assert enriched.masking_pattern == "HASH"

    def test_enrich_non_pii(self):
        col = Column(name="amount", bigquery_type=BigQueryType.FLOAT64)
        enriched = self.service.enrich_column(col)
        assert enriched.pii_category is None
        assert enriched is col  # Same object returned

    def test_enrich_already_tagged(self):
        col = Column(name="msisdn", bigquery_type=BigQueryType.STRING,
                    pii_category=PIICategory.MSISDN, policy_tag="existing")
        enriched = self.service.enrich_column(col)
        assert enriched is col  # Already tagged, don't override


class TestPartitioningService:
    def setup_method(self):
        self.service = PartitioningService()

    def test_apply_cdr_partitioning(self):
        table = Table(name="cdr", telco_domain=TelcoDomain.CDR_EVENT)
        result = self.service.apply_partitioning(table)
        assert result.partitioning is not None
        assert result.partitioning.column_name == "event_date"
        assert result.partitioning.partition_type == "DAY"

    def test_apply_subscriber_partitioning(self):
        table = Table(name="sub", telco_domain=TelcoDomain.SUBSCRIBER)
        result = self.service.apply_partitioning(table)
        assert result.partitioning.column_name == "activation_date"

    def test_apply_invoice_partitioning(self):
        table = Table(name="inv", telco_domain=TelcoDomain.REVENUE_INVOICE)
        result = self.service.apply_partitioning(table)
        assert result.partitioning.column_name == "bill_cycle_date"
        assert result.partitioning.partition_type == "MONTH"

    def test_preserves_existing_partitioning(self):
        existing = PartitioningStrategy(column_name="custom_date")
        table = Table(name="t", telco_domain=TelcoDomain.CDR_EVENT, partitioning=existing)
        result = self.service.apply_partitioning(table)
        assert result.partitioning.column_name == "custom_date"

    def test_apply_clustering(self):
        table = Table(name="cdr", telco_domain=TelcoDomain.CDR_EVENT)
        result = self.service.apply_clustering(table)
        assert result.clustering is not None
        assert "subscriber_id" in result.clustering.column_names

    def test_apply_all(self):
        table = Table(name="cdr", telco_domain=TelcoDomain.CDR_EVENT)
        result = self.service.apply_all(table)
        assert result.partitioning is not None
        assert result.clustering is not None

    def test_get_strategies(self):
        p = self.service.get_partition_strategy(TelcoDomain.CDR_EVENT)
        assert p is not None
        c = self.service.get_clustering_strategy(TelcoDomain.CDR_EVENT)
        assert c is not None


class TestComplianceService:
    def setup_method(self):
        self.service = ComplianceService()

    def test_clean_dataset_passes(self, sample_column):
        table = Table(name="clean", telco_domain=TelcoDomain.SUBSCRIBER, columns=(sample_column,))
        ds = Dataset(
            name="test", telco_domain=TelcoDomain.SUBSCRIBER, tables=(table,),
            jurisdiction=Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                                     gcp_region="me-central1", data_residency_required=True),
            gcp_region="me-central1",
        )
        rules = (ComplianceRule(
            rule_id="SA-001", jurisdiction="SA", framework="PDPL",
            applicable_pii_categories=(PIICategory.MSISDN,),
            data_residency_required=True, encryption_required=True,
        ),)
        report = self.service.evaluate(ds, rules)
        assert report.passed
        assert report.finding_count == 0

    def test_data_residency_violation(self, sample_table):
        ds = Dataset(
            name="test", telco_domain=TelcoDomain.SUBSCRIBER, tables=(sample_table,),
            jurisdiction=Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                                     gcp_region="me-central1", data_residency_required=True),
            gcp_region="us-central1",  # Wrong region!
        )
        rules = (ComplianceRule(
            rule_id="SA-001", jurisdiction="SA", framework="PDPL",
            applicable_pii_categories=(PIICategory.MSISDN,),
            data_residency_required=True,
        ),)
        report = self.service.evaluate(ds, rules)
        assert not report.passed
        assert any("residency" in f.description.lower() for f in report.findings)

    def test_missing_policy_tag(self):
        col = Column(name="msisdn", bigquery_type=BigQueryType.STRING,
                    pii_category=PIICategory.MSISDN)  # No policy_tag
        table = Table(name="t", telco_domain=TelcoDomain.SUBSCRIBER, columns=(col,))
        ds = Dataset(
            name="test", telco_domain=TelcoDomain.SUBSCRIBER, tables=(table,),
            jurisdiction=Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                                     gcp_region="me-central1", data_residency_required=False),
            gcp_region="me-central1",
        )
        rules = (ComplianceRule(
            rule_id="SA-002", jurisdiction="SA", framework="PDPL",
            applicable_pii_categories=(PIICategory.MSISDN,),
        ),)
        report = self.service.evaluate(ds, rules)
        assert not report.passed
        assert any("policy tag" in f.description.lower() for f in report.findings)

    def test_pii_inventory(self, sample_table):
        ds = Dataset(
            name="test", telco_domain=TelcoDomain.SUBSCRIBER, tables=(sample_table,),
            gcp_region="me-central1",
        )
        report = self.service.evaluate(ds, ())
        assert "subscriber_profile" in report.pii_inventory
        assert "msisdn" in report.pii_inventory["subscriber_profile"]


class TestMappingResolutionService:
    def setup_method(self):
        self.service = MappingResolutionService()

    def test_full_coverage(self):
        col = Column(name="subscriber_id", bigquery_type=BigQueryType.STRING)
        table = Table(name="subscriber_profile", telco_domain=TelcoDomain.SUBSCRIBER, columns=(col,))
        mappings = (VendorMapping(
            vendor=BSSVendor.AMDOCS, vendor_table="CM_SUB", vendor_field="SUB_ID",
            canonical_table="subscriber_profile", canonical_field="subscriber_id",
        ),)
        coverage = self.service.resolve(mappings, (table,))
        assert coverage.coverage_pct == 100.0
        assert len(coverage.unmapped_fields) == 0

    def test_partial_coverage(self):
        cols = (
            Column(name="subscriber_id", bigquery_type=BigQueryType.STRING),
            Column(name="status", bigquery_type=BigQueryType.STRING),
        )
        table = Table(name="sub", telco_domain=TelcoDomain.SUBSCRIBER, columns=cols)
        mappings = (VendorMapping(
            vendor=BSSVendor.AMDOCS, vendor_table="CM_SUB", vendor_field="SUB_ID",
            canonical_table="sub", canonical_field="subscriber_id",
        ),)
        coverage = self.service.resolve(mappings, (table,))
        assert coverage.coverage_pct == 50.0
        assert "sub.status" in coverage.unmapped_fields

    def test_conflict_detection(self):
        col = Column(name="subscriber_id", bigquery_type=BigQueryType.STRING)
        table = Table(name="sub", telco_domain=TelcoDomain.SUBSCRIBER, columns=(col,))
        mappings = (
            VendorMapping(vendor=BSSVendor.AMDOCS, vendor_table="T1", vendor_field="F1",
                         canonical_table="sub", canonical_field="subscriber_id"),
            VendorMapping(vendor=BSSVendor.AMDOCS, vendor_table="T2", vendor_field="F2",
                         canonical_table="sub", canonical_field="subscriber_id"),
        )
        coverage = self.service.resolve(mappings, (table,))
        assert len(coverage.conflicts) == 1

    def test_filter_by_confidence(self):
        mappings = (
            VendorMapping(vendor=BSSVendor.AMDOCS, vendor_table="T1", vendor_field="F1",
                         canonical_table="sub", canonical_field="f1", confidence=0.9),
            VendorMapping(vendor=BSSVendor.AMDOCS, vendor_table="T1", vendor_field="F2",
                         canonical_table="sub", canonical_field="f2", confidence=0.5),
        )
        filtered = self.service.filter_by_confidence(mappings, 0.8)
        assert len(filtered) == 1
        assert filtered[0].canonical_field == "f1"


class TestSchemaService:
    def setup_method(self):
        self.service = SchemaService()

    def test_build_table(self):
        cols = [
            {"name": "id", "type": "STRING", "description": "Primary key"},
            {"name": "amount", "type": "FLOAT64", "nullable": "false"},
        ]
        table = self.service.build_table("test_table", TelcoDomain.SUBSCRIBER, cols)
        assert table.name == "test_table"
        assert len(table.columns) == 2
        assert table.columns[0].bigquery_type == BigQueryType.STRING
        assert not table.columns[1].nullable

    def test_build_dataset(self):
        table = Table(name="t", telco_domain=TelcoDomain.SUBSCRIBER)
        jurisdiction = Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                                   gcp_region="me-central1", data_residency_required=True)
        ds = self.service.build_dataset("test_ds", TelcoDomain.SUBSCRIBER, (table,), jurisdiction)
        assert ds.name == "test_ds"
        assert ds.gcp_region == "me-central1"
        assert ds.kms_key_required  # Because jurisdiction requires data residency
