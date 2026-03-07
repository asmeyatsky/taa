"""Map Vendor Schema command."""

from __future__ import annotations

from taa.application.dtos.models import MappingResult
from taa.domain.ports.repositories import DomainModelRepositoryPort, VendorMappingRepositoryPort
from taa.domain.services.mapping_resolution import MappingResolutionService
from taa.domain.value_objects.enums import TelcoDomain, BSSVendor


class MapVendorSchemaCommand:
    """Load vendor mappings, resolve against canonical schema, return coverage."""

    def __init__(
        self,
        domain_repo: DomainModelRepositoryPort,
        vendor_repo: VendorMappingRepositoryPort,
        mapping_service: MappingResolutionService | None = None,
    ) -> None:
        self._domain_repo = domain_repo
        self._vendor_repo = vendor_repo
        self._mapping_service = mapping_service or MappingResolutionService()

    def execute(self, vendor_name: str, domain_name: str) -> MappingResult:
        vendor = BSSVendor(vendor_name)
        domain = TelcoDomain(domain_name)

        tables = self._domain_repo.load_tables(domain)
        mappings = self._vendor_repo.load_mappings(vendor, domain)
        coverage = self._mapping_service.resolve(mappings, tables)

        return MappingResult(
            vendor=vendor_name,
            domain=domain_name,
            total_fields=coverage.total_canonical_fields,
            mapped_fields=coverage.mapped_fields,
            coverage_pct=coverage.coverage_pct,
            unmapped_fields=list(coverage.unmapped_fields),
            conflicts=len(coverage.conflicts),
        )
