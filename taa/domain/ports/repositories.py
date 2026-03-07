"""Repository port interfaces."""

from __future__ import annotations

from typing import Protocol

from taa.domain.entities.table import Table
from taa.domain.entities.compliance_rule import ComplianceRule
from taa.domain.entities.vendor_mapping import VendorMapping
from taa.domain.value_objects.enums import TelcoDomain, BSSVendor


class DomainModelRepositoryPort(Protocol):
    """Port for loading pre-built domain model definitions."""

    def load_tables(self, domain: TelcoDomain) -> tuple[Table, ...]: ...

    def list_domains(self) -> tuple[TelcoDomain, ...]: ...


class ComplianceRuleRepositoryPort(Protocol):
    """Port for loading compliance rules."""

    def load_rules(self, jurisdiction_code: str) -> tuple[ComplianceRule, ...]: ...

    def list_jurisdictions(self) -> tuple[str, ...]: ...


class VendorMappingRepositoryPort(Protocol):
    """Port for loading vendor schema mappings."""

    def load_mappings(self, vendor: BSSVendor, domain: TelcoDomain) -> tuple[VendorMapping, ...]: ...

    def list_vendors(self) -> tuple[BSSVendor, ...]: ...
