"""TAA domain events."""

from taa.domain.events.base import DomainEvent
from taa.domain.events.generation_events import (
    SchemaAssembled,
    DDLGenerated,
    TerraformGenerated,
    PipelineGenerated,
    DAGGenerated,
)
from taa.domain.events.compliance_events import PIIDetected, ComplianceReportGenerated
from taa.domain.events.mapping_events import VendorMappingResolved, MappingConflictDetected

__all__ = [
    "DomainEvent",
    "SchemaAssembled",
    "DDLGenerated",
    "TerraformGenerated",
    "PipelineGenerated",
    "DAGGenerated",
    "PIIDetected",
    "ComplianceReportGenerated",
    "VendorMappingResolved",
    "MappingConflictDetected",
]
