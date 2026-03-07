"""AnalyticsTemplate entity."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.value_objects.enums import TemplateType


@dataclass(frozen=True)
class AnalyticsTemplate:
    """A pre-built analytics template definition."""

    name: str
    template_type: TemplateType
    required_tables: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
