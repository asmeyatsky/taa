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
