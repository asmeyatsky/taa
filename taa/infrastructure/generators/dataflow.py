"""Dataflow pipeline generator."""

from __future__ import annotations

from taa.domain.entities.pipeline import Pipeline
from taa.domain.value_objects.enums import PipelineType
from taa.infrastructure.template_renderer.jinja_renderer import JinjaRenderer

_PIPELINE_TEMPLATES: dict[PipelineType, str] = {
    PipelineType.BATCH_INGESTION: "dataflow/batch_ingestion.py.j2",
    PipelineType.CDR_MEDIATION: "dataflow/cdr_mediation.py.j2",
    PipelineType.CDC: "dataflow/cdc.py.j2",
    PipelineType.TAP_RAP: "dataflow/tap_rap.py.j2",
    PipelineType.REVENUE_ASSURANCE: "dataflow/revenue_assurance.py.j2",
}


class DataflowPipelineGenerator:
    """Generates Dataflow pipeline code from Pipeline entities."""

    def __init__(self, renderer: JinjaRenderer | None = None) -> None:
        self._renderer = renderer or JinjaRenderer()

    def generate(self, pipeline: Pipeline) -> str:
        template_name = _PIPELINE_TEMPLATES.get(pipeline.pipeline_type)
        if template_name is None:
            raise ValueError(f"No template for pipeline type: {pipeline.pipeline_type}")
        return self._renderer.render(template_name, {"pipeline": pipeline})
