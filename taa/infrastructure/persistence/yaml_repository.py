"""YAML-based domain model repository."""

from __future__ import annotations

from pathlib import Path

import yaml

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.entities.compliance_rule import ComplianceRule
from taa.domain.value_objects.enums import TelcoDomain, BigQueryType, PIICategory


DOMAIN_DATA_DIR = Path(__file__).parent.parent / "domain_data"
COMPLIANCE_RULES_DIR = Path(__file__).parent.parent / "compliance_rules"


class YAMLDomainModelRepository:
    """Loads pre-built domain model definitions from YAML files."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or DOMAIN_DATA_DIR

    def load_tables(self, domain: TelcoDomain) -> tuple[Table, ...]:
        yaml_path = self._data_dir / f"{domain.value}.yaml"
        if not yaml_path.exists():
            return ()

        with open(yaml_path) as f:
            data = yaml.safe_load(f)

        tables: list[Table] = []
        for table_def in data.get("tables", []):
            columns: list[Column] = []
            for col_def in table_def.get("columns", []):
                raw_type = col_def.get("type", "STRING")
                if raw_type == "BOOLEAN":
                    raw_type = "BOOL"
                columns.append(Column(
                    name=col_def["name"],
                    bigquery_type=BigQueryType(raw_type),
                    description=col_def.get("description", ""),
                    nullable=col_def.get("nullable", True),
                ))
            tables.append(Table(
                name=table_def["name"],
                telco_domain=domain,
                columns=tuple(columns),
                dataset_name=f"{domain.value}_ds",
            ))
        return tuple(tables)

    def list_domains(self) -> tuple[TelcoDomain, ...]:
        domains: list[TelcoDomain] = []
        for domain in TelcoDomain:
            yaml_path = self._data_dir / f"{domain.value}.yaml"
            if yaml_path.exists():
                domains.append(domain)
        return tuple(domains)


class YAMLComplianceRuleRepository:
    """Loads compliance rules from YAML files."""

    def __init__(self, rules_dir: Path | None = None) -> None:
        self._rules_dir = rules_dir or COMPLIANCE_RULES_DIR

    def load_rules(self, jurisdiction_code: str) -> tuple[ComplianceRule, ...]:
        # Find matching file
        for yaml_path in self._rules_dir.glob("*.yaml"):
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            if data.get("jurisdiction") == jurisdiction_code:
                return self._parse_rules(data)
        return ()

    def list_jurisdictions(self) -> tuple[str, ...]:
        jurisdictions: list[str] = []
        for yaml_path in sorted(self._rules_dir.glob("*.yaml")):
            with open(yaml_path) as f:
                data = yaml.safe_load(f)
            jurisdictions.append(data["jurisdiction"])
        return tuple(jurisdictions)

    def _parse_rules(self, data: dict) -> tuple[ComplianceRule, ...]:
        rules: list[ComplianceRule] = []
        for rule_def in data.get("rules", []):
            pii_cats = tuple(
                PIICategory(c) for c in rule_def.get("applicable_pii_categories", [])
            )
            rules.append(ComplianceRule(
                rule_id=rule_def["rule_id"],
                jurisdiction=data["jurisdiction"],
                framework=data["framework"],
                applicable_pii_categories=pii_cats,
                data_residency_required=rule_def.get("data_residency_required", False),
                encryption_required=rule_def.get("encryption_required", False),
                kms_rotation_days=rule_def.get("kms_rotation_days", 90),
                retention_months=rule_def.get("retention_months", 12),
            ))
        return tuple(rules)
