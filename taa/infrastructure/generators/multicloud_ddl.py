"""Multi-cloud DDL generator."""

from __future__ import annotations

from taa.domain.entities.table import Table
from taa.domain.entities.dataset import Dataset
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer


class AWSRedshiftDDLGenerator:
    """Generates Amazon Redshift DDL statements."""

    def __init__(self, renderer: JinjaRenderer | None = None) -> None:
        self._renderer = renderer or JinjaRenderer()

    def generate(self, tables: tuple[Table, ...], dataset_name: str) -> str:
        return self._renderer.render("aws/redshift_ddl.sql.j2", {
            "tables": tables,
            "dataset_name": dataset_name,
            "domain": tables[0].telco_domain.value if tables else "",
        })


class AWSCloudFormationGenerator:
    """Generates AWS CloudFormation templates."""

    def __init__(self, renderer: JinjaRenderer | None = None, project_id: str = "telco-analytics") -> None:
        self._renderer = renderer or JinjaRenderer()
        self._project_id = project_id

    def generate(self, datasets: tuple[Dataset, ...]) -> dict[str, str]:
        context = {
            "datasets": datasets,
            "project_id": self._project_id,
        }
        return {"cloudformation.yaml": self._renderer.render("aws/cloudformation.yaml.j2", context)}


class AzureSynapseDDLGenerator:
    """Generates Azure Synapse Analytics DDL statements."""

    def __init__(self, renderer: JinjaRenderer | None = None) -> None:
        self._renderer = renderer or JinjaRenderer()

    def generate(self, tables: tuple[Table, ...], dataset_name: str) -> str:
        return self._renderer.render("azure/synapse_ddl.sql.j2", {
            "tables": tables,
            "dataset_name": dataset_name,
            "domain": tables[0].telco_domain.value if tables else "",
        })


class AzureBicepGenerator:
    """Generates Azure Bicep infrastructure templates."""

    def __init__(self, renderer: JinjaRenderer | None = None, project_id: str = "telco-analytics") -> None:
        self._renderer = renderer or JinjaRenderer()
        self._project_id = project_id

    def generate(self, datasets: tuple[Dataset, ...]) -> dict[str, str]:
        region = datasets[0].gcp_region if datasets else "westeurope"
        has_residency = any(
            d.jurisdiction and d.jurisdiction.data_residency_required for d in datasets
        )
        context = {
            "datasets": datasets,
            "project_id": self._project_id,
            "region": region,
            "has_residency_requirement": has_residency,
        }
        return {"main.bicep": self._renderer.render("azure/bicep.bicep.j2", context)}
