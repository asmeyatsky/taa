"""Tests for domain value objects."""

import pytest

from taa.domain.value_objects.enums import (
    TelcoDomain, BSSVendor, PIICategory, BigQueryType,
    PipelineMode, PipelineType, TemplateType,
)
from taa.domain.value_objects.types import (
    Jurisdiction, PartitioningStrategy, ClusteringStrategy,
    PolicyTag, DAGSchedule, MaskingPattern,
)


class TestTelcoDomain:
    def test_has_seven_domains(self):
        assert len(TelcoDomain) == 7

    def test_values(self):
        assert TelcoDomain.SUBSCRIBER.value == "subscriber"
        assert TelcoDomain.CDR_EVENT.value == "cdr_event"
        assert TelcoDomain.REVENUE_INVOICE.value == "revenue_invoice"

    def test_string_enum(self):
        assert str(TelcoDomain.SUBSCRIBER) == "TelcoDomain.SUBSCRIBER"
        assert TelcoDomain("subscriber") == TelcoDomain.SUBSCRIBER


class TestBSSVendor:
    def test_has_four_vendors(self):
        assert len(BSSVendor) == 4

    def test_values(self):
        assert BSSVendor.AMDOCS.value == "amdocs"
        assert BSSVendor.HUAWEI_CBS.value == "huawei_cbs"
        assert BSSVendor.ORACLE_BRM.value == "oracle_brm"
        assert BSSVendor.ERICSSON_BSCS.value == "ericsson_bscs"


class TestPIICategory:
    def test_has_ten_categories(self):
        assert len(PIICategory) == 10

    def test_values(self):
        assert PIICategory.MSISDN.value == "msisdn"
        assert PIICategory.IMSI.value == "imsi"
        assert PIICategory.EMAIL.value == "email"


class TestBigQueryType:
    def test_has_fourteen_types(self):
        assert len(BigQueryType) == 14

    def test_values(self):
        assert BigQueryType.STRING.value == "STRING"
        assert BigQueryType.INT64.value == "INT64"
        assert BigQueryType.TIMESTAMP.value == "TIMESTAMP"


class TestJurisdiction:
    def test_frozen(self):
        j = Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                        gcp_region="me-central1", data_residency_required=True)
        with pytest.raises(AttributeError):
            j.code = "AE"

    def test_equality(self):
        j1 = Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                         gcp_region="me-central1", data_residency_required=True)
        j2 = Jurisdiction(code="SA", name="Saudi Arabia", primary_framework="PDPL",
                         gcp_region="me-central1", data_residency_required=True)
        assert j1 == j2


class TestPartitioningStrategy:
    def test_defaults(self):
        p = PartitioningStrategy(column_name="event_date")
        assert p.partition_type == "DAY"

    def test_custom_type(self):
        p = PartitioningStrategy(column_name="bill_cycle_date", partition_type="MONTH")
        assert p.partition_type == "MONTH"


class TestClusteringStrategy:
    def test_valid_columns(self):
        c = ClusteringStrategy(column_names=("a", "b", "c", "d"))
        assert len(c.column_names) == 4

    def test_max_four_columns(self):
        with pytest.raises(ValueError, match="maximum of 4"):
            ClusteringStrategy(column_names=("a", "b", "c", "d", "e"))


class TestPolicyTag:
    def test_full_path(self):
        pt = PolicyTag(taxonomy_id="projects/telco/locations/global/taxonomies/pii", tag_id="msisdn")
        assert pt.full_path == "projects/telco/locations/global/taxonomies/pii/policyTags/msisdn"


class TestDAGSchedule:
    def test_defaults(self):
        s = DAGSchedule(cron_expression="0 2 * * *")
        assert s.timezone == "UTC"


class TestMaskingPattern:
    def test_hash_pattern(self):
        m = MaskingPattern(pattern_type="HASH", hash_algorithm="SHA256")
        assert m.pattern_type == "HASH"
        assert m.hash_algorithm == "SHA256"

    def test_redact_pattern(self):
        m = MaskingPattern(pattern_type="REDACT")
        assert m.hash_algorithm is None
