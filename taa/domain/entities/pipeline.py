"""Pipeline entity."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.value_objects.enums import TelcoDomain, PipelineType, PipelineMode, BSSVendor


@dataclass(frozen=True)
class Pipeline:
    """A Dataflow pipeline definition."""

    name: str
    pipeline_type: PipelineType
    source_vendor: BSSVendor | None = None
    target_tables: tuple[str, ...] = ()
    mode: PipelineMode = PipelineMode.BATCH
    telco_domain: TelcoDomain | None = None
