"""Tests for cost estimation engine."""

import pytest

from taa.infrastructure.cost_estimation import CostEstimator, CostEstimate
from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import TelcoDomain, BigQueryType


@pytest.fixture
def sample_tables():
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


class TestCostEstimator:
    def test_gcp_estimate(self, sample_tables):
        estimator = CostEstimator()
        result = estimator.estimate(
            tables=sample_tables,
            subscriber_count=1_000_000,
            monthly_cdr_volume_gb=500,
            cloud_provider="gcp",
        )
        assert result.cloud_provider == "GCP"
        assert result.total_monthly_usd > 0
        assert result.total_annual_usd > 0
        assert result.total_annual_usd == pytest.approx(result.total_monthly_usd * 12, abs=1)
        assert len(result.breakdowns) >= 5

    def test_aws_estimate(self, sample_tables):
        estimator = CostEstimator()
        result = estimator.estimate(
            tables=sample_tables,
            cloud_provider="aws",
        )
        assert result.cloud_provider == "AWS"
        assert result.total_monthly_usd > 0

    def test_azure_estimate(self, sample_tables):
        estimator = CostEstimator()
        result = estimator.estimate(
            tables=sample_tables,
            cloud_provider="azure",
        )
        assert result.cloud_provider == "Azure"
        assert result.total_monthly_usd > 0

    def test_invalid_provider(self, sample_tables):
        estimator = CostEstimator()
        with pytest.raises(ValueError, match="Unknown cloud"):
            estimator.estimate(tables=sample_tables, cloud_provider="alibaba")

    def test_scales_with_volume(self, sample_tables):
        estimator = CostEstimator()
        small = estimator.estimate(tables=sample_tables, monthly_cdr_volume_gb=100)
        large = estimator.estimate(tables=sample_tables, monthly_cdr_volume_gb=10000)
        assert large.total_monthly_usd > small.total_monthly_usd

    def test_markdown_report(self, sample_tables):
        estimator = CostEstimator()
        result = estimator.estimate(tables=sample_tables)
        md = result.to_markdown()
        assert "# TAA Cloud Cost Estimation Report" in md
        assert "GCP" in md
        assert "TOTAL" in md
        assert "$" in md

    def test_breakdowns_have_services(self, sample_tables):
        estimator = CostEstimator()
        result = estimator.estimate(tables=sample_tables, cloud_provider="gcp")
        services = [b.service for b in result.breakdowns]
        assert "BigQuery Storage" in services
        assert "Dataflow Pipelines" in services
        assert "Cloud Composer" in services
