"""BigQuery DDL generator."""

from __future__ import annotations

from taa.domain.entities.table import Table
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer


class BigQueryDDLGenerator:
    """Generates BigQuery DDL statements from Table entities."""

    def __init__(self, renderer: JinjaRenderer | None = None, project_id: str = "telco-analytics") -> None:
        self._renderer = renderer or JinjaRenderer()
        self._project_id = project_id

    def generate(self, tables: tuple[Table, ...], dataset_name: str) -> str:
        table_ddls: dict[str, str] = {}
        for table in tables:
            table_ddls[table.name] = self.generate_table(table)

        return self._renderer.render("bigquery/dataset_ddl.sql.j2", {
            "dataset_name": dataset_name,
            "domain": tables[0].telco_domain.value if tables else "",
            "tables": tables,
            "table_ddl": table_ddls,
        })

    def generate_table(self, table: Table) -> str:
        return self._renderer.render("bigquery/create_table.sql.j2", {
            "table": table,
            "project_id": self._project_id,
            "dataset_name": table.dataset_name or f"{table.telco_domain.value}_ds",
        })
