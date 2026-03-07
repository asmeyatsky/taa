"""Generation-related domain events."""

from __future__ import annotations

from dataclasses import dataclass, field

from taa.domain.events.base import DomainEvent
from taa.domain.value_objects.enums import TelcoDomain


@dataclass(frozen=True)
class SchemaAssembled(DomainEvent):
    """Emitted when a domain schema has been assembled."""

    domain: TelcoDomain = TelcoDomain.SUBSCRIBER
    table_count: int = 0
    column_count: int = 0


@dataclass(frozen=True)
class DDLGenerated(DomainEvent):
    """Emitted when DDL has been generated."""

    domain: TelcoDomain = TelcoDomain.SUBSCRIBER
    table_count: int = 0
    output_path: str = ""


@dataclass(frozen=True)
class TerraformGenerated(DomainEvent):
    """Emitted when Terraform files have been generated."""

    file_count: int = 0
    output_path: str = ""


@dataclass(frozen=True)
class PipelineGenerated(DomainEvent):
    """Emitted when a Dataflow pipeline has been generated."""

    pipeline_name: str = ""
    output_path: str = ""


@dataclass(frozen=True)
class DAGGenerated(DomainEvent):
    """Emitted when an Airflow DAG has been generated."""

    dag_id: str = ""
    output_path: str = ""
