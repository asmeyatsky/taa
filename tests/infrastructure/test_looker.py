"""Tests for Looker Studio dashboard generator."""

from __future__ import annotations

import json

import pytest

from taa.infrastructure.generators.looker import LookerDashboardGenerator


@pytest.fixture()
def generator() -> LookerDashboardGenerator:
    return LookerDashboardGenerator(project_id="test-project")


class TestLookerDashboardGenerator:
    def test_list_templates(self, generator):
        templates = generator.list_templates()
        assert "revenue_assurance" in templates
        assert "churn_analytics" in templates
        assert "five_g_monetisation" in templates
        assert "roaming_interconnect" in templates
        assert len(templates) == 4

    def test_generate_revenue_assurance(self, generator):
        content = generator.generate("revenue_assurance")
        config = json.loads(content)
        assert config["title"] == "Revenue Assurance Dashboard"
        assert len(config["data_sources"]) >= 1
        assert len(config["pages"]) >= 1
        assert len(config["pages"][0]["charts"]) >= 3

    def test_generate_churn_analytics(self, generator):
        content = generator.generate("churn_analytics")
        config = json.loads(content)
        assert config["title"] == "Churn Analytics Dashboard"

    def test_generate_five_g_monetisation(self, generator):
        content = generator.generate("five_g_monetisation")
        config = json.loads(content)
        assert "5G" in config["title"]

    def test_generate_roaming_interconnect(self, generator):
        content = generator.generate("roaming_interconnect")
        config = json.loads(content)
        assert "Roaming" in config["title"]

    def test_unknown_template_raises(self, generator):
        with pytest.raises(ValueError, match="Unknown dashboard template"):
            generator.generate("nonexistent")

    def test_project_id_in_queries(self, generator):
        content = generator.generate("revenue_assurance")
        assert "test-project" in content

    def test_generate_all(self, generator):
        all_dashboards = generator.generate_all()
        assert len(all_dashboards) == 4
        assert "revenue_assurance_dashboard.json" in all_dashboards
        assert "churn_analytics_dashboard.json" in all_dashboards
        assert "five_g_monetisation_dashboard.json" in all_dashboards
        assert "roaming_interconnect_dashboard.json" in all_dashboards

    def test_all_dashboards_valid_json(self, generator):
        for name, content in generator.generate_all().items():
            config = json.loads(content)
            assert "title" in config, f"{name} missing title"
            assert "data_sources" in config, f"{name} missing data_sources"
            assert "pages" in config, f"{name} missing pages"

    def test_data_sources_have_bigquery_config(self, generator):
        content = generator.generate("revenue_assurance")
        config = json.loads(content)
        for ds in config["data_sources"]:
            assert ds["type"] == "bigquery"
            assert "project" in ds
            assert "dataset" in ds
            assert "table" in ds

    def test_charts_have_queries(self, generator):
        content = generator.generate("revenue_assurance")
        config = json.loads(content)
        for page in config["pages"]:
            for chart in page["charts"]:
                assert "type" in chart
                assert "title" in chart
                assert "query" in chart

    def test_generated_by_tag(self, generator):
        content = generator.generate("churn_analytics")
        config = json.loads(content)
        assert "TAA" in config["generated_by"]
