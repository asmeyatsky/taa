"""Compliance domain service."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.entities.dataset import Dataset
from taa.domain.entities.compliance_rule import ComplianceRule
from taa.domain.value_objects.enums import PIICategory


@dataclass(frozen=True)
class ComplianceFinding:
    """A single compliance finding."""

    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    remediation: str


@dataclass(frozen=True)
class ComplianceReport:
    """Result of compliance evaluation."""

    jurisdiction: str
    framework: str
    findings: tuple[ComplianceFinding, ...]
    pii_inventory: dict[str, list[str]]  # table_name -> [column_names]
    passed: bool

    @property
    def finding_count(self) -> int:
        return len(self.findings)


class ComplianceService:
    """Evaluates datasets against jurisdiction compliance rules."""

    def evaluate(
        self,
        dataset: Dataset,
        rules: tuple[ComplianceRule, ...],
    ) -> ComplianceReport:
        """Evaluate a dataset against compliance rules."""
        findings: list[ComplianceFinding] = []
        pii_inventory: dict[str, list[str]] = {}

        # Build PII inventory
        for table in dataset.tables:
            pii_cols = table.pii_columns()
            if pii_cols:
                pii_inventory[table.name] = [c.name for c in pii_cols]

        for rule in rules:
            findings.extend(self._evaluate_rule(dataset, rule, pii_inventory))

        jurisdiction = dataset.jurisdiction.code if dataset.jurisdiction else ""
        framework = dataset.jurisdiction.primary_framework if dataset.jurisdiction else ""

        return ComplianceReport(
            jurisdiction=jurisdiction,
            framework=framework,
            findings=tuple(findings),
            pii_inventory=pii_inventory,
            passed=len(findings) == 0,
        )

    def _evaluate_rule(
        self,
        dataset: Dataset,
        rule: ComplianceRule,
        pii_inventory: dict[str, list[str]],
    ) -> list[ComplianceFinding]:
        findings: list[ComplianceFinding] = []

        has_applicable_pii = self._has_applicable_pii(dataset, rule)

        if rule.data_residency_required and dataset.jurisdiction:
            if dataset.gcp_region != dataset.jurisdiction.gcp_region:
                findings.append(ComplianceFinding(
                    rule_id=rule.rule_id,
                    severity="CRITICAL",
                    description=f"Data residency violation: dataset in {dataset.gcp_region}, required {dataset.jurisdiction.gcp_region}",
                    remediation=f"Move dataset to {dataset.jurisdiction.gcp_region}",
                ))

        if rule.encryption_required and has_applicable_pii:
            if not dataset.requires_encryption():
                findings.append(ComplianceFinding(
                    rule_id=rule.rule_id,
                    severity="HIGH",
                    description="Dataset contains PII but encryption is not enabled",
                    remediation="Enable KMS encryption for the dataset",
                ))

        if has_applicable_pii:
            for table in dataset.tables:
                for col in table.pii_columns():
                    if col.pii_category in rule.applicable_pii_categories and not col.policy_tag:
                        findings.append(ComplianceFinding(
                            rule_id=rule.rule_id,
                            severity="HIGH",
                            description=f"PII column {table.name}.{col.name} ({col.pii_category.value}) missing policy tag",
                            remediation=f"Add policy tag for {col.pii_category.value} PII category",
                        ))

        return findings

    def _has_applicable_pii(self, dataset: Dataset, rule: ComplianceRule) -> bool:
        for table in dataset.tables:
            for col in table.pii_columns():
                if col.pii_category in rule.applicable_pii_categories:
                    return True
        return False
