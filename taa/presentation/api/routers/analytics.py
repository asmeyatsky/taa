"""Analytics template endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from taa.infrastructure.config.container import Container
from taa.infrastructure.generators.analytics import AnalyticsTemplateGenerator
from taa.infrastructure.generators.notebook import NotebookGenerator
from taa.infrastructure.generators.looker import LookerDashboardGenerator
from taa.presentation.api.dependencies import get_container
from taa.presentation.api.schemas import AnalyticsTemplateInfo

router = APIRouter()


@router.get("/templates")
def list_templates(container: Container = Depends(get_container)) -> list[AnalyticsTemplateInfo]:
    """List all available analytics templates, notebooks, and dashboards."""
    sql_gen = AnalyticsTemplateGenerator(container.renderer)
    nb_gen = NotebookGenerator()
    dash_gen = LookerDashboardGenerator()

    items: list[AnalyticsTemplateInfo] = []
    for name in sql_gen.list_templates():
        items.append(AnalyticsTemplateInfo(name=name, type="sql"))
    for name in nb_gen.list_templates():
        items.append(AnalyticsTemplateInfo(name=name, type="notebook"))
    for name in dash_gen.list_templates():
        items.append(AnalyticsTemplateInfo(name=name, type="dashboard"))

    return items


@router.post("/generate")
def generate_template(
    name: str,
    template_type: str = "sql",
    container: Container = Depends(get_container),
) -> dict:
    """Generate an analytics template by name and return its content."""
    if template_type == "sql":
        gen = AnalyticsTemplateGenerator(container.renderer)
        content = gen.generate(name)
        return {"name": name, "type": "sql", "content": content}
    elif template_type == "notebook":
        gen = NotebookGenerator()
        content = gen.generate(name)
        return {"name": name, "type": "notebook", "content": content}
    elif template_type == "dashboard":
        gen = LookerDashboardGenerator()
        content = gen.generate(name)
        return {"name": name, "type": "dashboard", "content": content}
    else:
        return {"error": f"Unknown type: {template_type}"}
