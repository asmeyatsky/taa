"""Compliance-related domain events."""

from __future__ import annotations

from dataclasses import dataclass, field

from taa.domain.events.base import DomainEvent
from taa.domain.value_objects.enums import PIICategory


@dataclass(frozen=True)
class PIIDetected(DomainEvent):
    """Emitted when PII is detected in a column."""

    table_name: str = ""
    column_name: str = ""
    pii_category: PIICategory = PIICategory.MSISDN


@dataclass(frozen=True)
class ComplianceReportGenerated(DomainEvent):
    """Emitted when a compliance report has been generated."""

    jurisdiction: str = ""
    finding_count: int = 0
    output_path: str = ""
