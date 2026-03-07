"""Cost estimation engine — estimates cloud infrastructure costs based on domain selection and data volumes."""

from __future__ import annotations

from dataclasses import dataclass, field

from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.domain.value_objects.enums import TelcoDomain


@dataclass(frozen=True)
class CostBreakdown:
    """Cost breakdown for a single service."""

    service: str
    description: str
    monthly_cost_usd: float
    annual_cost_usd: float
    unit: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0


@dataclass(frozen=True)
class CostEstimate:
    """Complete cost estimate for a TAA deployment."""

    cloud_provider: str
    region: str
    subscriber_count: int
    monthly_cdr_volume_gb: float
    breakdowns: tuple[CostBreakdown, ...]
    assumptions: tuple[str, ...]

    @property
    def total_monthly_usd(self) -> float:
        return sum(b.monthly_cost_usd for b in self.breakdowns)

    @property
    def total_annual_usd(self) -> float:
        return sum(b.annual_cost_usd for b in self.breakdowns)

    def to_markdown(self) -> str:
        lines = [
            "# TAA Cloud Cost Estimation Report",
            "",
            "## Parameters",
            "",
            f"| Parameter | Value |",
            f"|-----------|-------|",
            f"| Cloud Provider | {self.cloud_provider} |",
            f"| Region | {self.region} |",
            f"| Subscriber Count | {self.subscriber_count:,} |",
            f"| Monthly CDR Volume | {self.monthly_cdr_volume_gb:,.1f} GB |",
            "",
            "## Cost Breakdown",
            "",
            "| Service | Description | Monthly (USD) | Annual (USD) |",
            "|---------|-------------|---------------|--------------|",
        ]
        for b in self.breakdowns:
            lines.append(
                f"| {b.service} | {b.description} | ${b.monthly_cost_usd:,.2f} | ${b.annual_cost_usd:,.2f} |"
            )
        lines.extend([
            f"| **TOTAL** | | **${self.total_monthly_usd:,.2f}** | **${self.total_annual_usd:,.2f}** |",
            "",
            "## Assumptions",
            "",
        ])
        for a in self.assumptions:
            lines.append(f"- {a}")
        lines.append("")
        lines.append("*Note: These are estimates based on published pricing. Actual costs may vary based on "
                      "committed use discounts, negotiated rates, and actual usage patterns.*")
        return "\n".join(lines)


# GCP pricing constants (as of 2026, approximate)
_GCP_PRICING = {
    "bq_storage_per_gb_month": 0.02,        # Active storage
    "bq_long_term_per_gb_month": 0.01,       # Long-term storage (>90 days)
    "bq_query_per_tb": 6.25,                 # On-demand query pricing
    "bq_streaming_per_gb": 0.05,             # Streaming inserts
    "dataflow_vcpu_per_hr": 0.056,           # Per vCPU-hour
    "dataflow_memory_per_gb_hr": 0.003557,   # Per GB-hour
    "dataflow_storage_per_gb_hr": 0.000054,  # Per GB-hour (PD)
    "gcs_storage_per_gb_month": 0.02,        # Standard storage
    "kms_key_per_month": 0.06,               # Per key version
    "kms_operations_per_10k": 0.03,          # Per 10,000 operations
    "composer_env_per_hr": 0.35,             # Small Composer environment
    "vertex_notebook_per_hr": 0.38,          # n1-standard-4
    "cloud_monitoring_per_metric": 0.0,      # Free tier (first 150 metrics)
}

# AWS pricing constants (approximate)
_AWS_PRICING = {
    "redshift_dc2_per_hr": 0.25,             # dc2.large per node
    "s3_storage_per_gb_month": 0.023,
    "glue_dpu_per_hr": 0.44,
    "kms_key_per_month": 1.00,
}

# Azure pricing constants (approximate)
_AZURE_PRICING = {
    "synapse_dwu_per_hr": 1.20,             # DW100c
    "blob_storage_per_gb_month": 0.018,
    "data_factory_per_activity": 0.001,
    "key_vault_per_10k_ops": 0.03,
}


class CostEstimator:
    """Estimates cloud infrastructure costs for a TAA deployment."""

    def estimate(
        self,
        tables: tuple[Table, ...],
        subscriber_count: int = 1_000_000,
        monthly_cdr_volume_gb: float = 500.0,
        cloud_provider: str = "gcp",
        region: str = "me-central1",
        retention_months: int = 24,
    ) -> CostEstimate:
        """Estimate costs based on domain models, data volumes, and cloud provider."""
        if cloud_provider == "gcp":
            return self._estimate_gcp(tables, subscriber_count, monthly_cdr_volume_gb, region, retention_months)
        elif cloud_provider == "aws":
            return self._estimate_aws(tables, subscriber_count, monthly_cdr_volume_gb, region, retention_months)
        elif cloud_provider == "azure":
            return self._estimate_azure(tables, subscriber_count, monthly_cdr_volume_gb, region, retention_months)
        else:
            raise ValueError(f"Unknown cloud provider: {cloud_provider}")

    def _estimate_gcp(
        self, tables: tuple[Table, ...], subs: int, cdr_gb: float,
        region: str, retention_months: int,
    ) -> CostEstimate:
        p = _GCP_PRICING
        breakdowns: list[CostBreakdown] = []
        assumptions: list[str] = []

        # BigQuery storage
        # Estimate: subscriber data ~0.5KB/row, CDR ~0.2KB/row
        sub_tables = [t for t in tables if t.telco_domain == TelcoDomain.SUBSCRIBER]
        sub_storage_gb = subs * 0.5 / 1024  # KB per row → GB
        active_storage_gb = sub_storage_gb + cdr_gb * min(retention_months, 3)
        longterm_storage_gb = cdr_gb * max(retention_months - 3, 0)
        total_storage_gb = active_storage_gb + longterm_storage_gb

        bq_active_cost = active_storage_gb * p["bq_storage_per_gb_month"]
        bq_longterm_cost = longterm_storage_gb * p["bq_long_term_per_gb_month"]
        breakdowns.append(CostBreakdown(
            service="BigQuery Storage",
            description=f"{total_storage_gb:,.0f} GB ({active_storage_gb:,.0f} active + {longterm_storage_gb:,.0f} long-term)",
            monthly_cost_usd=bq_active_cost + bq_longterm_cost,
            annual_cost_usd=(bq_active_cost + bq_longterm_cost) * 12,
            unit="GB", quantity=total_storage_gb,
        ))

        # BigQuery queries (estimate: 5 TB/month of queries)
        query_tb = max(total_storage_gb / 200, 5)  # Scan estimate
        bq_query_cost = query_tb * p["bq_query_per_tb"]
        breakdowns.append(CostBreakdown(
            service="BigQuery Queries",
            description=f"~{query_tb:,.1f} TB/month on-demand scans",
            monthly_cost_usd=bq_query_cost,
            annual_cost_usd=bq_query_cost * 12,
            unit="TB", quantity=query_tb,
        ))

        # BigQuery streaming inserts (CDR data)
        streaming_cost = cdr_gb * p["bq_streaming_per_gb"]
        breakdowns.append(CostBreakdown(
            service="BigQuery Streaming",
            description=f"CDR streaming inserts ({cdr_gb:,.0f} GB/month)",
            monthly_cost_usd=streaming_cost,
            annual_cost_usd=streaming_cost * 12,
        ))

        # Dataflow (assume 4 vCPU workers, 16GB RAM, 24/7 for CDR)
        workers = max(int(cdr_gb / 200), 2)  # Scale workers with volume
        vcpu_hours = workers * 4 * 730  # 730 hrs/month
        mem_gb_hours = workers * 16 * 730
        df_cost = (vcpu_hours * p["dataflow_vcpu_per_hr"] +
                   mem_gb_hours * p["dataflow_memory_per_gb_hr"])
        breakdowns.append(CostBreakdown(
            service="Dataflow Pipelines",
            description=f"{workers} workers x 4 vCPU, 16GB RAM (24/7)",
            monthly_cost_usd=df_cost,
            annual_cost_usd=df_cost * 12,
        ))

        # Cloud Storage (landing zone + archives)
        gcs_gb = cdr_gb * 2  # Landing + processed
        gcs_cost = gcs_gb * p["gcs_storage_per_gb_month"]
        breakdowns.append(CostBreakdown(
            service="Cloud Storage",
            description=f"Landing zone + archives ({gcs_gb:,.0f} GB)",
            monthly_cost_usd=gcs_cost,
            annual_cost_usd=gcs_cost * 12,
        ))

        # KMS
        num_keys = len(set(t.telco_domain for t in tables))
        kms_cost = num_keys * p["kms_key_per_month"]
        breakdowns.append(CostBreakdown(
            service="Cloud KMS",
            description=f"{num_keys} encryption keys",
            monthly_cost_usd=kms_cost,
            annual_cost_usd=kms_cost * 12,
        ))

        # Composer
        composer_cost = p["composer_env_per_hr"] * 730
        breakdowns.append(CostBreakdown(
            service="Cloud Composer",
            description="Small environment (Airflow)",
            monthly_cost_usd=composer_cost,
            annual_cost_usd=composer_cost * 12,
        ))

        # Vertex AI notebook
        notebook_hrs = 160  # ~8 hrs/day, 20 days/month
        vertex_cost = notebook_hrs * p["vertex_notebook_per_hr"]
        breakdowns.append(CostBreakdown(
            service="Vertex AI Notebook",
            description="n1-standard-4 (~160 hrs/month)",
            monthly_cost_usd=vertex_cost,
            annual_cost_usd=vertex_cost * 12,
        ))

        assumptions.extend([
            f"Subscriber count: {subs:,}",
            f"Monthly CDR volume: {cdr_gb:,.0f} GB",
            f"Data retention: {retention_months} months",
            f"Average row size: subscriber ~0.5KB, CDR ~0.2KB",
            f"Query volume: ~{query_tb:,.1f} TB/month (on-demand pricing)",
            f"Dataflow: {workers} always-on workers",
            "Pricing based on GCP published rates (no committed use discounts)",
            "Network egress costs not included",
        ])

        return CostEstimate(
            cloud_provider="GCP",
            region=region,
            subscriber_count=subs,
            monthly_cdr_volume_gb=cdr_gb,
            breakdowns=tuple(breakdowns),
            assumptions=tuple(assumptions),
        )

    def _estimate_aws(
        self, tables: tuple[Table, ...], subs: int, cdr_gb: float,
        region: str, retention_months: int,
    ) -> CostEstimate:
        p = _AWS_PRICING
        breakdowns: list[CostBreakdown] = []

        # Redshift
        nodes = max(int(cdr_gb * retention_months / 2000), 2)  # ~2TB per node
        redshift_cost = nodes * p["redshift_dc2_per_hr"] * 730
        breakdowns.append(CostBreakdown(
            service="Amazon Redshift",
            description=f"{nodes} x dc2.large nodes",
            monthly_cost_usd=redshift_cost,
            annual_cost_usd=redshift_cost * 12,
        ))

        # S3
        s3_gb = cdr_gb * retention_months + subs * 0.5 / 1024
        s3_cost = s3_gb * p["s3_storage_per_gb_month"]
        breakdowns.append(CostBreakdown(
            service="Amazon S3",
            description=f"{s3_gb:,.0f} GB storage",
            monthly_cost_usd=s3_cost,
            annual_cost_usd=s3_cost * 12,
        ))

        # Glue
        glue_dpus = max(int(cdr_gb / 100), 2)
        glue_hrs = 730  # Continuous
        glue_cost = glue_dpus * glue_hrs * p["glue_dpu_per_hr"]
        breakdowns.append(CostBreakdown(
            service="AWS Glue",
            description=f"{glue_dpus} DPUs for ETL",
            monthly_cost_usd=glue_cost,
            annual_cost_usd=glue_cost * 12,
        ))

        # KMS
        num_keys = len(set(t.telco_domain for t in tables))
        kms_cost = num_keys * p["kms_key_per_month"]
        breakdowns.append(CostBreakdown(
            service="AWS KMS",
            description=f"{num_keys} encryption keys",
            monthly_cost_usd=kms_cost,
            annual_cost_usd=kms_cost * 12,
        ))

        return CostEstimate(
            cloud_provider="AWS",
            region=region,
            subscriber_count=subs,
            monthly_cdr_volume_gb=cdr_gb,
            breakdowns=tuple(breakdowns),
            assumptions=(
                f"Subscriber count: {subs:,}",
                f"Monthly CDR volume: {cdr_gb:,.0f} GB",
                f"Data retention: {retention_months} months",
                "Redshift dc2.large on-demand pricing",
                "Glue DPU on-demand pricing",
            ),
        )

    def _estimate_azure(
        self, tables: tuple[Table, ...], subs: int, cdr_gb: float,
        region: str, retention_months: int,
    ) -> CostEstimate:
        p = _AZURE_PRICING
        breakdowns: list[CostBreakdown] = []

        # Synapse
        synapse_cost = p["synapse_dwu_per_hr"] * 730
        breakdowns.append(CostBreakdown(
            service="Azure Synapse",
            description="DW100c dedicated SQL pool",
            monthly_cost_usd=synapse_cost,
            annual_cost_usd=synapse_cost * 12,
        ))

        # Blob Storage
        blob_gb = cdr_gb * retention_months + subs * 0.5 / 1024
        blob_cost = blob_gb * p["blob_storage_per_gb_month"]
        breakdowns.append(CostBreakdown(
            service="Azure Blob Storage",
            description=f"{blob_gb:,.0f} GB",
            monthly_cost_usd=blob_cost,
            annual_cost_usd=blob_cost * 12,
        ))

        # Data Factory
        activities = cdr_gb * 1000  # Rough estimate
        adf_cost = activities * p["data_factory_per_activity"]
        breakdowns.append(CostBreakdown(
            service="Azure Data Factory",
            description="ETL pipeline orchestration",
            monthly_cost_usd=adf_cost,
            annual_cost_usd=adf_cost * 12,
        ))

        # Key Vault
        kv_cost = 10 * p["key_vault_per_10k_ops"]  # Estimate 100k ops
        breakdowns.append(CostBreakdown(
            service="Azure Key Vault",
            description="Encryption key management",
            monthly_cost_usd=kv_cost,
            annual_cost_usd=kv_cost * 12,
        ))

        return CostEstimate(
            cloud_provider="Azure",
            region=region,
            subscriber_count=subs,
            monthly_cdr_volume_gb=cdr_gb,
            breakdowns=tuple(breakdowns),
            assumptions=(
                f"Subscriber count: {subs:,}",
                f"Monthly CDR volume: {cdr_gb:,.0f} GB",
                f"Data retention: {retention_months} months",
                "Synapse DW100c on-demand pricing",
                "Data Factory activity-based pricing",
            ),
        )
