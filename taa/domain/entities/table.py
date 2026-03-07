"""Table entity - core aggregate."""

from __future__ import annotations

from dataclasses import dataclass, field

from taa.domain.entities.column import Column
from taa.domain.value_objects.enums import TelcoDomain
from taa.domain.value_objects.types import PartitioningStrategy, ClusteringStrategy


@dataclass(frozen=True)
class Table:
    """A BigQuery table definition - core domain aggregate."""

    name: str
    telco_domain: TelcoDomain
    columns: tuple[Column, ...] = ()
    partitioning: PartitioningStrategy | None = None
    clustering: ClusteringStrategy | None = None
    dataset_name: str = ""

    def add_column(self, column: Column) -> Table:
        """Return a new Table with the column added."""
        return Table(
            name=self.name,
            telco_domain=self.telco_domain,
            columns=(*self.columns, column),
            partitioning=self.partitioning,
            clustering=self.clustering,
            dataset_name=self.dataset_name,
        )

    def pii_columns(self) -> tuple[Column, ...]:
        """Return all columns marked as PII."""
        return tuple(c for c in self.columns if c.is_pii)

    def has_pii(self) -> bool:
        """Check if any column is PII."""
        return any(c.is_pii for c in self.columns)
