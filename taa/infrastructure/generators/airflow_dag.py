"""Airflow DAG generator."""

from __future__ import annotations

from taa.domain.entities.dag import DAG
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer


class AirflowDAGGenerator:
    """Generates Airflow DAG code from DAG entities."""

    def __init__(self, renderer: JinjaRenderer | None = None) -> None:
        self._renderer = renderer or JinjaRenderer()

    def generate(self, dag: DAG) -> str:
        return self._renderer.render("airflow/dag.py.j2", {"dag": dag})
