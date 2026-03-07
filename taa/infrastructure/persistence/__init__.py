"""Persistence adapters."""

from taa.infrastructure.persistence.yaml_repository import (
    YAMLDomainModelRepository,
    YAMLComplianceRuleRepository,
)

__all__ = ["YAMLDomainModelRepository", "YAMLComplianceRuleRepository"]
