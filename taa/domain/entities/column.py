"""Column entity."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.value_objects.enums import BigQueryType, PIICategory


@dataclass(frozen=True)
class Column:
    """A BigQuery table column definition."""

    name: str
    bigquery_type: BigQueryType
    description: str = ""
    nullable: bool = True
    pii_category: PIICategory | None = None
    policy_tag: str | None = None
    masking_pattern: str | None = None

    @property
    def is_pii(self) -> bool:
        return self.pii_category is not None
