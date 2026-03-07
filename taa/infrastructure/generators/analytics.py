"""Analytics template generator."""

from __future__ import annotations

from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer

ANALYTICS_TEMPLATES = {
    "churn_prediction": "analytics/churn_prediction.sql.j2",
    "revenue_leakage": "analytics/revenue_leakage.sql.j2",
    "arpu_analysis": "analytics/arpu_analysis.sql.j2",
    "network_quality": "analytics/network_quality.sql.j2",
    "five_g_monetization": "analytics/five_g_monetization.sql.j2",
}


class AnalyticsTemplateGenerator:
    """Generates analytics SQL templates for BigQuery ML and Vertex AI."""

    def __init__(self, renderer: JinjaRenderer | None = None, project_id: str = "telco-analytics") -> None:
        self._renderer = renderer or JinjaRenderer()
        self._project_id = project_id

    def generate(self, template_name: str, dataset_name: str = "analytics_ds") -> str:
        template_path = ANALYTICS_TEMPLATES.get(template_name)
        if template_path is None:
            raise ValueError(f"Unknown analytics template: {template_name}. Available: {list(ANALYTICS_TEMPLATES.keys())}")
        return self._renderer.render(template_path, {
            "project_id": self._project_id,
            "dataset_name": dataset_name,
        })

    def generate_all(self, dataset_name: str = "analytics_ds") -> dict[str, str]:
        results = {}
        for name in ANALYTICS_TEMPLATES:
            results[name] = self.generate(name, dataset_name)
        return results

    def list_templates(self) -> list[str]:
        return list(ANALYTICS_TEMPLATES.keys())
