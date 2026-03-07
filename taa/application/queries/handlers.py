"""Application query handlers."""

from __future__ import annotations

from taa.application.dtos.models import DomainInfo, VendorInfo, JurisdictionInfo
from taa.domain.ports.repositories import (
    DomainModelRepositoryPort,
    VendorMappingRepositoryPort,
    ComplianceRuleRepositoryPort,
)
from taa.application.commands.generate_terraform import JURISDICTIONS


class ListDomainsQuery:
    """List all available telco domains."""

    def __init__(self, domain_repo: DomainModelRepositoryPort) -> None:
        self._domain_repo = domain_repo

    def execute(self) -> list[DomainInfo]:
        domains = self._domain_repo.list_domains()
        results = []
        for domain in domains:
            tables = self._domain_repo.load_tables(domain)
            results.append(DomainInfo(
                name=domain.value,
                table_count=len(tables),
                tables=[t.name for t in tables],
            ))
        return results


class GetDomainModelQuery:
    """Get detailed information about a specific domain."""

    def __init__(self, domain_repo: DomainModelRepositoryPort) -> None:
        self._domain_repo = domain_repo

    def execute(self, domain_name: str) -> DomainInfo:
        from taa.domain.value_objects.enums import TelcoDomain
        domain = TelcoDomain(domain_name)
        tables = self._domain_repo.load_tables(domain)
        return DomainInfo(
            name=domain.value,
            table_count=len(tables),
            tables=[t.name for t in tables],
        )


class ListVendorsQuery:
    """List all supported BSS vendors."""

    def __init__(self, vendor_repo: VendorMappingRepositoryPort) -> None:
        self._vendor_repo = vendor_repo

    def execute(self) -> list[VendorInfo]:
        vendors = self._vendor_repo.list_vendors()
        return [VendorInfo(name=v.value) for v in vendors]


class ListJurisdictionsQuery:
    """List all supported jurisdictions."""

    def __init__(self, compliance_repo: ComplianceRuleRepositoryPort) -> None:
        self._compliance_repo = compliance_repo

    def execute(self) -> list[JurisdictionInfo]:
        results = []
        for code, j in JURISDICTIONS.items():
            rules = self._compliance_repo.load_rules(code)
            results.append(JurisdictionInfo(
                code=j.code,
                name=j.name,
                framework=j.primary_framework,
                gcp_region=j.gcp_region,
                data_residency_required=j.data_residency_required,
                rule_count=len(rules),
            ))
        return results
