"""Schema assembly domain service."""

from __future__ import annotations

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.domain.value_objects.enums import TelcoDomain, BigQueryType
from taa.domain.value_objects.types import Jurisdiction


class SchemaService:
    """Assembles Table and Dataset entities from definitions."""

    def build_table(
        self,
        name: str,
        domain: TelcoDomain,
        column_defs: list[dict[str, str]],
        dataset_name: str = "",
    ) -> Table:
        """Build a Table entity from column definitions."""
        columns: list[Column] = []
        for col_def in column_defs:
            columns.append(Column(
                name=col_def["name"],
                bigquery_type=BigQueryType(col_def.get("type", "STRING")),
                description=col_def.get("description", ""),
                nullable=col_def.get("nullable", "true").lower() != "false" if isinstance(col_def.get("nullable"), str) else col_def.get("nullable", True),
            ))
        return Table(
            name=name,
            telco_domain=domain,
            columns=tuple(columns),
            dataset_name=dataset_name or f"{domain.value}_ds",
        )

    def build_dataset(
        self,
        name: str,
        domain: TelcoDomain,
        tables: tuple[Table, ...],
        jurisdiction: Jurisdiction | None = None,
        gcp_region: str = "",
    ) -> Dataset:
        """Build a Dataset entity."""
        kms_required = any(t.has_pii() for t in tables)
        if jurisdiction and jurisdiction.data_residency_required:
            kms_required = True
        return Dataset(
            name=name,
            telco_domain=domain,
            tables=tables,
            jurisdiction=jurisdiction,
            gcp_region=gcp_region or (jurisdiction.gcp_region if jurisdiction else ""),
            kms_key_required=kms_required,
        )
