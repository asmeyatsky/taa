"""E2E golden file regression tests for TAA.

Generates artefacts and compares them against known-good "golden" output files.
This ensures that changes don't accidentally break output.

First run:  UPDATE_GOLDEN=1 pytest tests/test_e2e_golden.py -v
            (creates the golden files)

Subsequent: pytest tests/test_e2e_golden.py -v
            (compares generated output against golden files)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from taa.infrastructure.config.container import Container
from taa.application.dtos.models import GenerationRequest
from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
from taa.infrastructure.generators.multicloud_ddl import (
    AWSRedshiftDDLGenerator,
    AzureSynapseDDLGenerator,
)
from taa.infrastructure.schema_import import SchemaParser, VendorDetector
from taa.infrastructure.cost_estimation import CostEstimator
from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import TelcoDomain, BigQueryType
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).parent / "golden"


def _update_golden() -> bool:
    """Check whether we should update (create/overwrite) golden files."""
    return os.environ.get("UPDATE_GOLDEN", "").strip() in ("1", "true", "yes")


def _assert_golden(golden_name: str, actual: str) -> None:
    """Compare *actual* output against the golden file.

    If UPDATE_GOLDEN is set, write *actual* as the new golden file instead of
    comparing.
    """
    golden_path = GOLDEN_DIR / golden_name
    if _update_golden():
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(actual, encoding="utf-8")
        # Still pass the test when updating.
        return

    assert golden_path.exists(), (
        f"Golden file not found: {golden_path}\n"
        f"Run with UPDATE_GOLDEN=1 to create it."
    )
    expected = golden_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"Output differs from golden file {golden_path}.\n"
        f"Run with UPDATE_GOLDEN=1 to update."
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def container() -> Container:
    return Container(project_id="telco-analytics")


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("golden_output")


@pytest.fixture(scope="module")
def renderer() -> JinjaRenderer:
    return JinjaRenderer()


@pytest.fixture(scope="module")
def sample_tables_for_cost() -> tuple[Table, ...]:
    return (
        Table(
            name="subscriber_profile",
            telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(
                Column(name="subscriber_id", bigquery_type=BigQueryType.STRING),
                Column(name="msisdn", bigquery_type=BigQueryType.STRING),
            ),
        ),
        Table(
            name="voice_cdr",
            telco_domain=TelcoDomain.CDR_EVENT,
            columns=(
                Column(name="cdr_id", bigquery_type=BigQueryType.STRING),
                Column(name="event_date", bigquery_type=BigQueryType.DATE),
            ),
        ),
    )


# ---------------------------------------------------------------------------
# (a) DDL generation – subscriber domain, SA jurisdiction
# ---------------------------------------------------------------------------

class TestDDLGolden:
    def test_subscriber_ddl_matches_golden(self, container: Container, output_dir: Path) -> None:
        request = GenerationRequest(
            domains=["subscriber"],
            jurisdiction="SA",
            output_dir=output_dir / "ddl_test",
        )
        result = container.generate_ddl.execute(request)

        assert result.success, f"DDL generation failed: {result.errors}"
        assert result.file_count >= 1

        ddl_path = Path(result.files_generated[0])
        actual = ddl_path.read_text(encoding="utf-8")

        # Sanity checks independent of golden file
        assert "CREATE TABLE" in actual
        assert "subscriber" in actual.lower()

        _assert_golden("subscriber_ddl.sql", actual)


# ---------------------------------------------------------------------------
# (b) Terraform generation – subscriber domain
# ---------------------------------------------------------------------------

class TestTerraformGolden:
    def test_subscriber_terraform_has_key_sections(
        self, container: Container, output_dir: Path
    ) -> None:
        request = GenerationRequest(
            domains=["subscriber"],
            jurisdiction="SA",
            output_dir=output_dir / "tf_test",
        )
        result = container.generate_terraform.execute(request)

        assert result.success, f"Terraform generation failed: {result.errors}"
        assert result.file_count >= 5

        # Combine all generated Terraform files for a composite golden file
        tf_dir = output_dir / "tf_test" / "terraform"
        tf_files_content: dict[str, str] = {}
        for fpath_str in sorted(result.files_generated):
            fpath = Path(fpath_str)
            tf_files_content[fpath.name] = fpath.read_text(encoding="utf-8")

        # Key sections that must be present
        all_content = "\n".join(tf_files_content.values())
        assert "google_bigquery_dataset" in all_content or "bigquery" in all_content.lower()
        assert "subscriber_ds" in all_content
        assert "variable" in all_content or "var." in all_content

        # Build deterministic composite for golden comparison
        composite = ""
        for fname in sorted(tf_files_content.keys()):
            composite += f"--- {fname} ---\n"
            composite += tf_files_content[fname]
            composite += "\n"

        _assert_golden("subscriber_terraform.txt", composite)


# ---------------------------------------------------------------------------
# (c) Compliance report – cdr_event domain, SA jurisdiction
# ---------------------------------------------------------------------------

class TestComplianceGolden:
    def test_cdr_event_compliance_structure(
        self, container: Container, output_dir: Path
    ) -> None:
        request = GenerationRequest(
            domains=["cdr_event"],
            jurisdiction="SA",
            output_dir=output_dir / "compliance_test",
        )
        result = container.generate_compliance.execute(request)

        assert result.success, f"Compliance generation failed: {result.errors}"
        assert result.file_count >= 2  # JSON + Markdown

        # Read both outputs
        json_files = [f for f in result.files_generated if f.endswith(".json")]
        md_files = [f for f in result.files_generated if f.endswith(".md")]
        assert len(json_files) >= 1
        assert len(md_files) >= 1

        json_content = Path(json_files[0]).read_text(encoding="utf-8")
        md_content = Path(md_files[0]).read_text(encoding="utf-8")

        # Structure checks
        assert "SA" in json_content or "PDPL" in json_content
        assert "cdr_event" in json_content.lower() or "cdr" in json_content.lower()

        _assert_golden("cdr_event_compliance.json", json_content)
        _assert_golden("cdr_event_compliance.md", md_content)


# ---------------------------------------------------------------------------
# (d) Full pack – subscriber + cdr_event
# ---------------------------------------------------------------------------

class TestFullPackGolden:
    def test_full_pack_file_count_and_content(
        self, container: Container, output_dir: Path
    ) -> None:
        request = GenerationRequest(
            domains=["subscriber", "cdr_event"],
            jurisdiction="SA",
            output_dir=output_dir / "fullpack_test",
        )
        result = container.generate_full_pack.execute(request)

        assert result.success, f"Full pack failed: {result.errors}"
        # DDL (2) + Terraform (12) + Pipelines + DAGs + Compliance (4) = many files
        assert result.file_count >= 10, (
            f"Expected at least 10 files, got {result.file_count}: {result.files_generated}"
        )

        # Verify key content exists in generated files
        all_files = {Path(f).name: Path(f).read_text(encoding="utf-8") for f in result.files_generated}

        # DDL files
        ddl_files = [n for n in all_files if n.endswith(".sql") and ("subscriber" in n or "cdr" in n)]
        assert len(ddl_files) >= 1, "Should have at least one domain DDL file"

        # Terraform files
        tf_files = [n for n in all_files if n.endswith(".tf")]
        assert len(tf_files) >= 5, f"Expected at least 5 .tf files, got {len(tf_files)}"

        # Compliance files
        compliance_files = [n for n in all_files if "compliance" in n]
        assert len(compliance_files) >= 2, "Should have compliance JSON and MD"

        # Save a manifest for golden comparison
        manifest_lines = sorted(all_files.keys())
        manifest = "\n".join(manifest_lines) + "\n"
        _assert_golden("fullpack_manifest.txt", manifest)


# ---------------------------------------------------------------------------
# (e) Analytics templates – all 5 produce valid SQL
# ---------------------------------------------------------------------------

class TestAnalyticsGolden:
    def test_all_analytics_templates_produce_valid_sql(self, renderer: JinjaRenderer) -> None:
        gen = AnalyticsTemplateGenerator(renderer, project_id="telco-analytics")
        results = gen.generate_all(dataset_name="analytics_ds")

        assert len(results) == 5, f"Expected 5 analytics templates, got {len(results)}"

        expected_templates = [
            "churn_prediction",
            "revenue_leakage",
            "arpu_analysis",
            "network_quality",
            "five_g_monetization",
        ]

        composite = ""
        for name in expected_templates:
            assert name in results, f"Missing analytics template: {name}"
            sql = results[name]

            # Validate it looks like SQL
            sql_upper = sql.upper()
            assert "SELECT" in sql_upper or "CREATE" in sql_upper, (
                f"Template '{name}' does not contain SELECT or CREATE"
            )

            composite += f"--- {name} ---\n"
            composite += sql
            composite += "\n"

        _assert_golden("analytics_templates.sql", composite)


# ---------------------------------------------------------------------------
# (f) AWS / Azure DDL – cloud-specific syntax
# ---------------------------------------------------------------------------

class TestMulticloudDDLGolden:
    @pytest.fixture()
    def subscriber_tables(self) -> tuple[Table, ...]:
        return (
            Table(
                name="subscriber_profile",
                telco_domain=TelcoDomain.SUBSCRIBER,
                columns=(
                    Column(name="subscriber_id", bigquery_type=BigQueryType.STRING, nullable=False),
                    Column(name="msisdn", bigquery_type=BigQueryType.STRING),
                    Column(name="status", bigquery_type=BigQueryType.STRING),
                    Column(name="activation_date", bigquery_type=BigQueryType.DATE),
                ),
                dataset_name="subscriber_ds",
            ),
        )

    def test_aws_redshift_ddl(self, renderer: JinjaRenderer, subscriber_tables: tuple[Table, ...]) -> None:
        gen = AWSRedshiftDDLGenerator(renderer)
        ddl = gen.generate(subscriber_tables, "subscriber_ds")

        assert "subscriber_profile" in ddl
        assert "subscriber_id" in ddl
        # Redshift-specific syntax markers
        assert "CREATE TABLE" in ddl.upper() or "CREATE" in ddl.upper()

        _assert_golden("aws_redshift_ddl.sql", ddl)

    def test_azure_synapse_ddl(self, renderer: JinjaRenderer, subscriber_tables: tuple[Table, ...]) -> None:
        gen = AzureSynapseDDLGenerator(renderer)
        ddl = gen.generate(subscriber_tables, "subscriber_ds")

        assert "subscriber_profile" in ddl
        assert "subscriber_id" in ddl
        assert "CREATE TABLE" in ddl.upper() or "CREATE" in ddl.upper()

        _assert_golden("azure_synapse_ddl.sql", ddl)


# ---------------------------------------------------------------------------
# (g) Schema import – parse sample DDL, detect vendor, count mappings
# ---------------------------------------------------------------------------

class TestSchemaImportGolden:
    SAMPLE_DDL = """\
CREATE TABLE CM_SUBSCRIBER (
    SUBSCRIBER_ID VARCHAR(50) NOT NULL,
    MSISDN VARCHAR(20),
    STATUS CHAR(1),
    ACTIVATION_DATE DATE NOT NULL
);

CREATE TABLE CM_ACCOUNT (
    ACCOUNT_ID VARCHAR(50) NOT NULL,
    ACCOUNT_NO VARCHAR(30),
    CUSTOMER_NAME VARCHAR(100)
);

CREATE TABLE AR_INVOICE (
    INVOICE_ID NUMBER NOT NULL,
    ACCOUNT_ID VARCHAR(50),
    AMOUNT NUMBER(12,2),
    INVOICE_DATE DATE
);
"""

    def test_schema_import_detection_and_mapping(self) -> None:
        # 1. Parse the DDL
        parser = SchemaParser()
        tables = parser.parse(self.SAMPLE_DDL, "ddl")

        assert len(tables) == 3
        table_names = sorted(t.name for t in tables)
        assert table_names == ["AR_INVOICE", "CM_ACCOUNT", "CM_SUBSCRIBER"]

        # Total column count
        total_cols = sum(len(t.columns) for t in tables)
        assert total_cols == 11

        # 2. Detect vendor
        detector = VendorDetector()
        detection = detector.detect(tables)

        # CM_ prefix tables are characteristic of Amdocs
        assert detection.vendor is not None, "Vendor should be detected"
        assert detection.vendor.value == "amdocs", (
            f"Expected Amdocs vendor, got {detection.vendor}"
        )
        assert detection.confidence >= 0.5

        # Build a report for golden comparison
        report_lines = [
            f"tables_parsed: {len(tables)}",
            f"table_names: {', '.join(table_names)}",
            f"total_columns: {total_cols}",
            f"detected_vendor: {detection.vendor.value if detection.vendor else 'unknown'}",
            f"vendor_confidence: {detection.confidence:.2f}",
        ]
        # Per-table column counts
        for t in sorted(tables, key=lambda x: x.name):
            col_names = ", ".join(c.name for c in t.columns)
            report_lines.append(f"  {t.name}: [{col_names}]")

        report = "\n".join(report_lines) + "\n"
        _assert_golden("schema_import_report.txt", report)


# ---------------------------------------------------------------------------
# (h) Cost estimation – verify reasonable cost ranges
# ---------------------------------------------------------------------------

class TestCostEstimationGolden:
    def test_gcp_cost_estimation(self, sample_tables_for_cost: tuple[Table, ...]) -> None:
        estimator = CostEstimator()
        result = estimator.estimate(
            tables=sample_tables_for_cost,
            subscriber_count=1_000_000,
            monthly_cdr_volume_gb=500,
            cloud_provider="gcp",
        )

        assert result.cloud_provider == "GCP"
        assert result.total_monthly_usd > 0
        assert result.total_annual_usd > 0
        assert result.total_annual_usd == pytest.approx(result.total_monthly_usd * 12, abs=1.0)

        # Reasonable range: monthly cost should be between $100 and $100,000
        assert 100 < result.total_monthly_usd < 100_000, (
            f"Monthly cost ${result.total_monthly_usd:.2f} seems unreasonable"
        )

        # Should have multiple service breakdowns
        assert len(result.breakdowns) >= 5

        # Build a report for golden comparison
        report_lines = [
            f"cloud_provider: {result.cloud_provider}",
            f"region: {result.region}",
            f"total_monthly_usd: {result.total_monthly_usd:.2f}",
            f"total_annual_usd: {result.total_annual_usd:.2f}",
            f"breakdown_count: {len(result.breakdowns)}",
            "breakdowns:",
        ]
        for b in result.breakdowns:
            report_lines.append(
                f"  - {b.service}: ${b.monthly_cost_usd:.2f}/mo (${b.annual_cost_usd:.2f}/yr)"
            )

        report = "\n".join(report_lines) + "\n"
        _assert_golden("cost_estimation_gcp.txt", report)

    def test_aws_cost_estimation(self, sample_tables_for_cost: tuple[Table, ...]) -> None:
        estimator = CostEstimator()
        result = estimator.estimate(
            tables=sample_tables_for_cost,
            subscriber_count=1_000_000,
            monthly_cdr_volume_gb=500,
            cloud_provider="aws",
        )

        assert result.cloud_provider == "AWS"
        assert result.total_monthly_usd > 0
        assert 100 < result.total_monthly_usd < 100_000

        report_lines = [
            f"cloud_provider: {result.cloud_provider}",
            f"total_monthly_usd: {result.total_monthly_usd:.2f}",
            f"total_annual_usd: {result.total_annual_usd:.2f}",
            f"breakdown_count: {len(result.breakdowns)}",
        ]
        report = "\n".join(report_lines) + "\n"
        _assert_golden("cost_estimation_aws.txt", report)

    def test_azure_cost_estimation(self, sample_tables_for_cost: tuple[Table, ...]) -> None:
        estimator = CostEstimator()
        result = estimator.estimate(
            tables=sample_tables_for_cost,
            subscriber_count=1_000_000,
            monthly_cdr_volume_gb=500,
            cloud_provider="azure",
        )

        assert result.cloud_provider == "Azure"
        assert result.total_monthly_usd > 0
        assert 100 < result.total_monthly_usd < 100_000

        report_lines = [
            f"cloud_provider: {result.cloud_provider}",
            f"total_monthly_usd: {result.total_monthly_usd:.2f}",
            f"total_annual_usd: {result.total_annual_usd:.2f}",
            f"breakdown_count: {len(result.breakdowns)}",
        ]
        report = "\n".join(report_lines) + "\n"
        _assert_golden("cost_estimation_azure.txt", report)
