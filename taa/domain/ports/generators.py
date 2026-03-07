"""Generator port interfaces."""

from __future__ import annotations

from typing import Protocol

from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.domain.entities.pipeline import Pipeline
from taa.domain.entities.dag import DAG
from taa.domain.services.compliance import ComplianceReport


class DDLGeneratorPort(Protocol):
    """Port for generating BigQuery DDL statements."""

    def generate(self, tables: tuple[Table, ...], dataset_name: str) -> str: ...

    def generate_table(self, table: Table) -> str: ...


class TerraformGeneratorPort(Protocol):
    """Port for generating Terraform configuration files."""

    def generate(self, datasets: tuple[Dataset, ...]) -> dict[str, str]: ...


class PipelineGeneratorPort(Protocol):
    """Port for generating Dataflow pipeline code."""

    def generate(self, pipeline: Pipeline) -> str: ...


class DAGGeneratorPort(Protocol):
    """Port for generating Airflow DAG code."""

    def generate(self, dag: DAG) -> str: ...


class ComplianceReportGeneratorPort(Protocol):
    """Port for generating compliance report documents."""

    def generate_json(self, report: ComplianceReport) -> str: ...

    def generate_markdown(self, report: ComplianceReport) -> str: ...
