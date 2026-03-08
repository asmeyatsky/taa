"""Looker Studio dashboard configuration generator."""

from __future__ import annotations

import json


def _revenue_assurance_dashboard(project_id: str, dataset: str) -> dict:
    return {
        "title": "Revenue Assurance Dashboard",
        "description": "Real-time leakage detection, unrated CDR monitoring, and revenue assurance KPIs.",
        "generated_by": "TAA (Telco Analytics Accelerator)",
        "data_sources": [
            {
                "name": "Revenue Assurance Flags",
                "type": "bigquery",
                "project": project_id,
                "dataset": "revenue_invoice_ds",
                "table": "revenue_assurance_flag",
            },
            {
                "name": "Voice CDRs",
                "type": "bigquery",
                "project": project_id,
                "dataset": "cdr_event_ds",
                "table": "voice_cdr",
            },
            {
                "name": "Invoices",
                "type": "bigquery",
                "project": project_id,
                "dataset": "revenue_invoice_ds",
                "table": "invoice",
            },
        ],
        "pages": [
            {
                "name": "Overview",
                "charts": [
                    {
                        "type": "scorecard",
                        "title": "Total Leakage (MTD)",
                        "query": f"SELECT SUM(leakage_amount) AS total_leakage FROM `{project_id}.revenue_invoice_ds.revenue_assurance_flag` WHERE DATE(created_at) >= DATE_TRUNC(CURRENT_DATE(), MONTH)",
                        "format": "currency_usd",
                    },
                    {
                        "type": "scorecard",
                        "title": "Unrated CDR Volume",
                        "query": f"SELECT COUNT(*) AS unrated FROM `{project_id}.cdr_event_ds.voice_cdr` WHERE rated_amount IS NULL AND event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)",
                        "format": "number",
                    },
                    {
                        "type": "time_series",
                        "title": "Leakage by Day",
                        "query": f"SELECT DATE(created_at) AS day, SUM(leakage_amount) AS daily_leakage FROM `{project_id}.revenue_invoice_ds.revenue_assurance_flag` WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) GROUP BY day ORDER BY day",
                        "x_axis": "day",
                        "y_axis": "daily_leakage",
                    },
                    {
                        "type": "bar_chart",
                        "title": "Leakage by Type",
                        "query": f"SELECT flag_type, SUM(leakage_amount) AS total FROM `{project_id}.revenue_invoice_ds.revenue_assurance_flag` WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) GROUP BY flag_type ORDER BY total DESC",
                        "dimension": "flag_type",
                        "metric": "total",
                    },
                    {
                        "type": "bar_chart",
                        "title": "Leakage by Product",
                        "query": f"SELECT product_id, SUM(leakage_amount) AS total FROM `{project_id}.revenue_invoice_ds.revenue_assurance_flag` WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) GROUP BY product_id ORDER BY total DESC LIMIT 10",
                        "dimension": "product_id",
                        "metric": "total",
                    },
                ],
            },
        ],
    }


def _churn_analytics_dashboard(project_id: str, dataset: str) -> dict:
    return {
        "title": "Churn Analytics Dashboard",
        "description": "Subscriber churn rate tracking, risk segmentation, and retention campaign ROI.",
        "generated_by": "TAA (Telco Analytics Accelerator)",
        "data_sources": [
            {
                "name": "Subscriber Profiles",
                "type": "bigquery",
                "project": project_id,
                "dataset": "subscriber_ds",
                "table": "subscriber_profile",
            },
            {
                "name": "Churn Features",
                "type": "bigquery",
                "project": project_id,
                "dataset": dataset,
                "table": "churn_features",
            },
        ],
        "pages": [
            {
                "name": "Churn Overview",
                "charts": [
                    {
                        "type": "scorecard",
                        "title": "Monthly Churn Rate",
                        "query": f"SELECT SAFE_DIVIDE(COUNTIF(status = 'terminated' AND deactivation_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)), COUNT(*)) * 100 AS churn_rate FROM `{project_id}.subscriber_ds.subscriber_profile`",
                        "format": "percent",
                    },
                    {
                        "type": "pie_chart",
                        "title": "Churn by Segment",
                        "query": f"SELECT segment, COUNT(*) AS churned FROM `{project_id}.subscriber_ds.subscriber_profile` WHERE status = 'terminated' AND deactivation_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) GROUP BY segment",
                        "dimension": "segment",
                        "metric": "churned",
                    },
                    {
                        "type": "histogram",
                        "title": "Churn Probability Distribution",
                        "query": f"SELECT ROUND(churn_risk_score, 1) AS risk_bucket, COUNT(*) AS subscribers FROM `{project_id}.subscriber_ds.subscriber_profile` WHERE status = 'active' GROUP BY risk_bucket ORDER BY risk_bucket",
                        "dimension": "risk_bucket",
                        "metric": "subscribers",
                    },
                    {
                        "type": "table",
                        "title": "Top Churn Drivers",
                        "query": f"SELECT segment, account_type, AVG(churn_risk_score) AS avg_risk, COUNT(*) AS subscribers FROM `{project_id}.subscriber_ds.subscriber_profile` WHERE status = 'active' GROUP BY segment, account_type ORDER BY avg_risk DESC LIMIT 20",
                    },
                ],
            },
        ],
    }


def _five_g_monetisation_dashboard(project_id: str, dataset: str) -> dict:
    return {
        "title": "5G Monetisation Dashboard",
        "description": "5G ARPU analysis, network slice revenue, device mix, and coverage correlation.",
        "generated_by": "TAA (Telco Analytics Accelerator)",
        "data_sources": [
            {
                "name": "5G NR Events",
                "type": "bigquery",
                "project": project_id,
                "dataset": "cdr_event_ds",
                "table": "five_g_nr_event",
            },
            {
                "name": "Network Slice Usage",
                "type": "bigquery",
                "project": project_id,
                "dataset": "usage_analytics_ds",
                "table": "network_slice_usage",
            },
        ],
        "pages": [
            {
                "name": "5G Revenue",
                "charts": [
                    {
                        "type": "scorecard",
                        "title": "5G ARPU",
                        "query": f"SELECT AVG(charge_amount) AS arpu_5g FROM `{project_id}.cdr_event_ds.five_g_nr_event` WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)",
                        "format": "currency_usd",
                    },
                    {
                        "type": "bar_chart",
                        "title": "5G vs 4G ARPU",
                        "query": f"SELECT technology, AVG(charge_amount) AS arpu FROM `{project_id}.cdr_event_ds.voice_cdr` WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY technology",
                        "dimension": "technology",
                        "metric": "arpu",
                    },
                    {
                        "type": "time_series",
                        "title": "Slice Revenue Trend",
                        "query": f"SELECT DATE(reporting_date) AS day, SUM(total_revenue) AS revenue FROM `{project_id}.usage_analytics_ds.network_slice_usage` WHERE reporting_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) GROUP BY day ORDER BY day",
                        "x_axis": "day",
                        "y_axis": "revenue",
                    },
                    {
                        "type": "pie_chart",
                        "title": "Device Mix (5G Capable)",
                        "query": f"SELECT device_type, COUNT(*) AS total FROM `{project_id}.subscriber_ds.subscriber_device` WHERE five_g_capable = TRUE GROUP BY device_type",
                        "dimension": "device_type",
                        "metric": "total",
                    },
                ],
            },
        ],
    }


def _roaming_interconnect_dashboard(project_id: str, dataset: str) -> dict:
    return {
        "title": "Roaming & Interconnect Dashboard",
        "description": "Roaming margin analysis, settlement variance, and IOT compliance tracking.",
        "generated_by": "TAA (Telco Analytics Accelerator)",
        "data_sources": [
            {
                "name": "Roaming CDRs",
                "type": "bigquery",
                "project": project_id,
                "dataset": "cdr_event_ds",
                "table": "roaming_cdr",
            },
            {
                "name": "Roaming Settlements",
                "type": "bigquery",
                "project": project_id,
                "dataset": "interconnect_roaming_ds",
                "table": "roaming_settlement",
            },
        ],
        "pages": [
            {
                "name": "Roaming Overview",
                "charts": [
                    {
                        "type": "scorecard",
                        "title": "Roaming Margin (MTD)",
                        "query": f"SELECT SUM(retail_charge - wholesale_cost) AS margin FROM `{project_id}.cdr_event_ds.roaming_cdr` WHERE event_timestamp >= TIMESTAMP(DATE_TRUNC(CURRENT_DATE(), MONTH))",
                        "format": "currency_usd",
                    },
                    {
                        "type": "bar_chart",
                        "title": "Margin by Partner",
                        "query": f"SELECT visited_network, SUM(retail_charge - wholesale_cost) AS margin FROM `{project_id}.cdr_event_ds.roaming_cdr` WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY) GROUP BY visited_network ORDER BY margin DESC LIMIT 15",
                        "dimension": "visited_network",
                        "metric": "margin",
                    },
                    {
                        "type": "time_series",
                        "title": "Settlement Variance",
                        "query": f"SELECT settlement_period, SUM(ABS(expected_amount - actual_amount)) AS variance FROM `{project_id}.interconnect_roaming_ds.roaming_settlement` GROUP BY settlement_period ORDER BY settlement_period",
                        "x_axis": "settlement_period",
                        "y_axis": "variance",
                    },
                    {
                        "type": "table",
                        "title": "IOT Compliance Rate by Partner",
                        "query": f"SELECT partner_operator, COUNTIF(iot_compliant = TRUE) / COUNT(*) * 100 AS compliance_rate, COUNT(*) AS total_records FROM `{project_id}.interconnect_roaming_ds.roaming_settlement` GROUP BY partner_operator ORDER BY compliance_rate ASC",
                    },
                ],
            },
        ],
    }


DASHBOARD_TEMPLATES = {
    "revenue_assurance": _revenue_assurance_dashboard,
    "churn_analytics": _churn_analytics_dashboard,
    "five_g_monetisation": _five_g_monetisation_dashboard,
    "roaming_interconnect": _roaming_interconnect_dashboard,
}


class LookerDashboardGenerator:
    """Generates Looker Studio dashboard configuration JSON files."""

    def __init__(self, project_id: str = "telco-analytics") -> None:
        self._project_id = project_id

    def generate(self, template_name: str, dataset_name: str = "analytics_ds") -> str:
        """Generate a single dashboard config as JSON."""
        builder = DASHBOARD_TEMPLATES.get(template_name)
        if builder is None:
            raise ValueError(
                f"Unknown dashboard template: {template_name}. "
                f"Available: {list(DASHBOARD_TEMPLATES.keys())}"
            )
        config = builder(self._project_id, dataset_name)
        return json.dumps(config, indent=2)

    def generate_all(self, dataset_name: str = "analytics_ds") -> dict[str, str]:
        """Generate all dashboards. Returns {filename: json_content}."""
        results = {}
        for name in DASHBOARD_TEMPLATES:
            results[f"{name}_dashboard.json"] = self.generate(name, dataset_name)
        return results

    def list_templates(self) -> list[str]:
        return list(DASHBOARD_TEMPLATES.keys())
