"""Extended tests for compliance report generator."""

from taa.infrastructure.generators.compliance_report import ComplianceReportGenerator
from taa.domain.services.compliance import ComplianceReport, ComplianceFinding


class TestComplianceReportGeneratorExtended:
    def setup_method(self):
        self.gen = ComplianceReportGenerator()

    def test_markdown_with_findings(self):
        report = ComplianceReport(
            jurisdiction="SA",
            framework="PDPL",
            findings=(
                ComplianceFinding(
                    rule_id="SA-001", severity="CRITICAL",
                    description="Data residency violation",
                    remediation="Move dataset to me-central1",
                ),
                ComplianceFinding(
                    rule_id="SA-002", severity="HIGH",
                    description="Missing encryption",
                    remediation="Enable KMS",
                ),
            ),
            pii_inventory={"subscriber_profile": ["msisdn", "imsi"]},
            passed=False,
        )
        md = self.gen.generate_markdown(report)
        assert "FAILED" in md
        assert "CRITICAL" in md
        assert "SA-001" in md
        assert "SA-002" in md
        assert "Data residency violation" in md
        assert "Move dataset to me-central1" in md
        assert "| subscriber_profile |" in md
        assert "msisdn" in md

    def test_json_with_findings(self):
        report = ComplianceReport(
            jurisdiction="AE",
            framework="PDPL",
            findings=(
                ComplianceFinding(
                    rule_id="AE-001", severity="HIGH",
                    description="Test finding",
                    remediation="Fix it",
                ),
            ),
            pii_inventory={"table1": ["col1"]},
            passed=False,
        )
        j = self.gen.generate_json(report)
        assert '"AE"' in j
        assert '"AE-001"' in j
        assert '"HIGH"' in j

    def test_empty_report(self):
        report = ComplianceReport(
            jurisdiction="EU", framework="GDPR",
            findings=(), pii_inventory={}, passed=True,
        )
        md = self.gen.generate_markdown(report)
        assert "PASSED" in md
        assert "## Findings" not in md  # No findings detail section when empty
