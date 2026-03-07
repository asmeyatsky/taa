"""Tests for application queries."""

from taa.application.queries.handlers import (
    ListDomainsQuery, GetDomainModelQuery, ListVendorsQuery, ListJurisdictionsQuery,
)
from taa.infrastructure.persistence.yaml_repository import (
    YAMLDomainModelRepository, YAMLComplianceRuleRepository,
)
from taa.infrastructure.vendor_mappings.readers import VendorSchemaReader


class TestListDomainsQuery:
    def test_execute(self):
        query = ListDomainsQuery(YAMLDomainModelRepository())
        result = query.execute()
        assert len(result) >= 6
        names = [d.name for d in result]
        assert "subscriber" in names
        assert "cdr_event" in names

    def test_includes_table_info(self):
        query = ListDomainsQuery(YAMLDomainModelRepository())
        result = query.execute()
        subscriber = next(d for d in result if d.name == "subscriber")
        assert subscriber.table_count >= 1
        assert "subscriber_profile" in subscriber.tables


class TestGetDomainModelQuery:
    def test_execute(self):
        query = GetDomainModelQuery(YAMLDomainModelRepository())
        result = query.execute("subscriber")
        assert result.name == "subscriber"
        assert result.table_count >= 1


class TestListVendorsQuery:
    def test_execute(self):
        query = ListVendorsQuery(VendorSchemaReader())
        result = query.execute()
        assert len(result) >= 1
        names = [v.name for v in result]
        assert "amdocs" in names


class TestListJurisdictionsQuery:
    def test_execute(self):
        query = ListJurisdictionsQuery(YAMLComplianceRuleRepository())
        result = query.execute()
        assert len(result) >= 1
        codes = [j.code for j in result]
        assert "SA" in codes

    def test_includes_details(self):
        query = ListJurisdictionsQuery(YAMLComplianceRuleRepository())
        result = query.execute()
        sa = next(j for j in result if j.code == "SA")
        assert sa.name == "Saudi Arabia"
        assert sa.framework == "PDPL"
        assert sa.data_residency_required is True
