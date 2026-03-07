"""ComplianceRule entity."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.value_objects.enums import PIICategory


@dataclass(frozen=True)
class ComplianceRule:
    """A compliance rule for a specific jurisdiction."""

    rule_id: str
    jurisdiction: str
    framework: str
    applicable_pii_categories: tuple[PIICategory, ...] = ()
    data_residency_required: bool = False
    encryption_required: bool = False
    kms_rotation_days: int = 90
    retention_months: int = 12
