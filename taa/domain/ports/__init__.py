"""TAA domain ports (Protocol interfaces)."""

from taa.domain.ports.generators import (
    DDLGeneratorPort,
    TerraformGeneratorPort,
    PipelineGeneratorPort,
    DAGGeneratorPort,
    ComplianceReportGeneratorPort,
)
from taa.domain.ports.repositories import (
    DomainModelRepositoryPort,
    ComplianceRuleRepositoryPort,
    VendorMappingRepositoryPort,
)
from taa.domain.ports.infrastructure import (
    TemplateRendererPort,
    OutputWriterPort,
)

__all__ = [
    "DDLGeneratorPort",
    "TerraformGeneratorPort",
    "PipelineGeneratorPort",
    "DAGGeneratorPort",
    "ComplianceReportGeneratorPort",
    "DomainModelRepositoryPort",
    "ComplianceRuleRepositoryPort",
    "VendorMappingRepositoryPort",
    "TemplateRendererPort",
    "OutputWriterPort",
]
