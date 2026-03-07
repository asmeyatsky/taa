"""Vendor mapping domain events."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.events.base import DomainEvent
from taa.domain.value_objects.enums import BSSVendor


@dataclass(frozen=True)
class VendorMappingResolved(DomainEvent):
    """Emitted when vendor mappings have been resolved."""

    vendor: BSSVendor = BSSVendor.AMDOCS
    mapping_count: int = 0
    coverage_pct: float = 0.0


@dataclass(frozen=True)
class MappingConflictDetected(DomainEvent):
    """Emitted when conflicting vendor mappings are found."""

    vendor: BSSVendor = BSSVendor.AMDOCS
    canonical_field: str = ""
    conflict_count: int = 0
