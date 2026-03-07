"""Tests for domain events."""

from taa.domain.events.base import DomainEvent
from taa.domain.events.generation_events import SchemaAssembled, DDLGenerated
from taa.domain.events.compliance_events import PIIDetected
from taa.domain.events.mapping_events import VendorMappingResolved
from taa.domain.value_objects.enums import TelcoDomain, PIICategory, BSSVendor


class TestDomainEvent:
    def test_has_event_id(self):
        event = DomainEvent()
        assert event.event_id is not None

    def test_has_timestamp(self):
        event = DomainEvent()
        assert event.occurred_at is not None

    def test_unique_ids(self):
        e1 = DomainEvent()
        e2 = DomainEvent()
        assert e1.event_id != e2.event_id


class TestGenerationEvents:
    def test_schema_assembled(self):
        event = SchemaAssembled(domain=TelcoDomain.CDR_EVENT, table_count=5, column_count=30)
        assert event.domain == TelcoDomain.CDR_EVENT
        assert event.table_count == 5

    def test_ddl_generated(self):
        event = DDLGenerated(domain=TelcoDomain.SUBSCRIBER, table_count=3, output_path="/tmp/ddl.sql")
        assert event.output_path == "/tmp/ddl.sql"


class TestComplianceEvents:
    def test_pii_detected(self):
        event = PIIDetected(table_name="sub", column_name="msisdn", pii_category=PIICategory.MSISDN)
        assert event.pii_category == PIICategory.MSISDN


class TestMappingEvents:
    def test_vendor_mapping_resolved(self):
        event = VendorMappingResolved(vendor=BSSVendor.AMDOCS, mapping_count=50, coverage_pct=85.5)
        assert event.coverage_pct == 85.5
