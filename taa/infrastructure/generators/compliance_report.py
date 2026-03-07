"""Compliance report generator."""

from __future__ import annotations

import json

from taa.domain.services.compliance import ComplianceReport


class ComplianceReportGenerator:
    """Generates compliance report documents."""

    def generate_json(self, report: ComplianceReport) -> str:
        data = {
            "jurisdiction": report.jurisdiction,
            "framework": report.framework,
            "passed": report.passed,
            "finding_count": report.finding_count,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "severity": f.severity,
                    "description": f.description,
                    "remediation": f.remediation,
                }
                for f in report.findings
            ],
            "pii_inventory": report.pii_inventory,
        }
        return json.dumps(data, indent=2)

    def generate_markdown(self, report: ComplianceReport) -> str:
        lines: list[str] = [
            f"# Compliance Report - {report.jurisdiction} ({report.framework})",
            "",
            f"**Status**: {'PASSED' if report.passed else 'FAILED'}",
            f"**Findings**: {report.finding_count}",
            "",
        ]

        if report.pii_inventory:
            lines.append("## PII Inventory")
            lines.append("")
            lines.append("| Table | PII Columns |")
            lines.append("|-------|------------|")
            for table, cols in report.pii_inventory.items():
                lines.append(f"| {table} | {', '.join(cols)} |")
            lines.append("")

        if report.findings:
            lines.append("## Findings")
            lines.append("")
            for f in report.findings:
                lines.append(f"### [{f.severity}] {f.rule_id}")
                lines.append("")
                lines.append(f"**Description**: {f.description}")
                lines.append("")
                lines.append(f"**Remediation**: {f.remediation}")
                lines.append("")

        return "\n".join(lines)

    def generate_retention_ddl(self, tables, rules, project_id="telco-analytics"):
        """Generate data retention enforcement SQL based on compliance rules."""
        policies = []
        max_retention = max((r.retention_months for r in rules), default=24)

        for table in tables:
            partition_col = table.partitioning.column_name if table.partitioning else None
            policies.append({
                "table_name": table.name,
                "dataset_name": table.dataset_name or f"{table.telco_domain.value}_ds",
                "partition_column": partition_col,
                "retention_months": max_retention,
                "framework": rules[0].framework if rules else "",
                "jurisdiction": rules[0].jurisdiction if rules else "",
            })

        # This would use a template, but for now return formatted SQL
        lines = [
            f"-- Data Retention Policy (max {max_retention} months)",
            f"-- Framework: {rules[0].framework if rules else 'N/A'}",
            "",
        ]
        for p in policies:
            if p["partition_column"]:
                lines.append(f"DELETE FROM `{project_id}.{p['dataset_name']}.{p['table_name']}`")
                lines.append(f"WHERE {p['partition_column']} < DATE_SUB(CURRENT_DATE(), INTERVAL {p['retention_months']} MONTH);")
                lines.append("")
        return "\n".join(lines)
