"""TAA domain value object types (frozen dataclasses)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Jurisdiction:
    """Legal jurisdiction with data residency requirements."""
    code: str
    name: str
    primary_framework: str
    gcp_region: str
    data_residency_required: bool


@dataclass(frozen=True)
class PartitioningStrategy:
    """BigQuery table partitioning strategy."""
    column_name: str
    partition_type: str = "DAY"


@dataclass(frozen=True)
class ClusteringStrategy:
    """BigQuery table clustering strategy (max 4 columns)."""
    column_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.column_names) > 4:
            raise ValueError("BigQuery clustering supports a maximum of 4 columns")


@dataclass(frozen=True)
class PolicyTag:
    """BigQuery column-level security policy tag."""
    taxonomy_id: str
    tag_id: str

    @property
    def full_path(self) -> str:
        return f"{self.taxonomy_id}/policyTags/{self.tag_id}"


@dataclass(frozen=True)
class DAGSchedule:
    """Airflow DAG schedule configuration."""
    cron_expression: str
    timezone: str = "UTC"


@dataclass(frozen=True)
class MaskingPattern:
    """Data masking pattern for PII columns."""
    pattern_type: str  # HASH, REDACT, PARTIAL_MASK, NULLIFY
    hash_algorithm: str | None = None
