"""Tests for infrastructure repositories."""

import pytest

from taa.domain.value_objects.enums import TelcoDomain, BSSVendor
from taa.infrastructure.persistence.yaml_repository import (
    YAMLDomainModelRepository,
    YAMLComplianceRuleRepository,
)
from taa.infrastructure.vendor_mappings.readers import VendorSchemaReader


class TestYAMLDomainModelRepository:
    def setup_method(self):
        self.repo = YAMLDomainModelRepository()

    def test_list_domains(self):
        domains = self.repo.list_domains()
        assert len(domains) >= 1
        assert TelcoDomain.SUBSCRIBER in domains

    def test_load_subscriber_tables(self):
        tables = self.repo.load_tables(TelcoDomain.SUBSCRIBER)
        assert len(tables) >= 1
        table_names = [t.name for t in tables]
        assert "subscriber_profile" in table_names

    def test_load_cdr_tables(self):
        tables = self.repo.load_tables(TelcoDomain.CDR_EVENT)
        assert len(tables) >= 1
        table_names = [t.name for t in tables]
        assert "voice_cdr" in table_names

    def test_tables_have_columns(self):
        tables = self.repo.load_tables(TelcoDomain.SUBSCRIBER)
        for table in tables:
            assert len(table.columns) > 0

    def test_nonexistent_domain(self):
        # usage_analytics has no yaml file
        tables = self.repo.load_tables(TelcoDomain.USAGE_ANALYTICS)
        assert tables == ()


class TestYAMLComplianceRuleRepository:
    def setup_method(self):
        self.repo = YAMLComplianceRuleRepository()

    def test_list_jurisdictions(self):
        jurisdictions = self.repo.list_jurisdictions()
        assert len(jurisdictions) >= 1
        assert "SA" in jurisdictions

    def test_load_saudi_rules(self):
        rules = self.repo.load_rules("SA")
        assert len(rules) >= 1
        assert all(r.jurisdiction == "SA" for r in rules)
        assert all(r.framework == "PDPL" for r in rules)

    def test_load_nonexistent(self):
        rules = self.repo.load_rules("XX")
        assert rules == ()


class TestVendorSchemaReader:
    def setup_method(self):
        self.reader = VendorSchemaReader()

    def test_list_vendors(self):
        vendors = self.reader.list_vendors()
        assert len(vendors) >= 1

    def test_load_amdocs_subscriber(self):
        mappings = self.reader.load_mappings(BSSVendor.AMDOCS, TelcoDomain.SUBSCRIBER)
        assert len(mappings) >= 1
        assert all(m.vendor == BSSVendor.AMDOCS for m in mappings)

    def test_load_nonexistent(self):
        mappings = self.reader.load_mappings(BSSVendor.AMDOCS, TelcoDomain.USAGE_ANALYTICS)
        assert mappings == ()
