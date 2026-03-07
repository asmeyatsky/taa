"""Dataset entity."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import TelcoDomain
from taa.domain.value_objects.types import Jurisdiction


@dataclass(frozen=True)
class Dataset:
    """A BigQuery dataset definition grouping tables for a domain/jurisdiction."""

    name: str
    telco_domain: TelcoDomain
    tables: tuple[Table, ...] = ()
    jurisdiction: Jurisdiction | None = None
    gcp_region: str = ""
    kms_key_required: bool = False

    def requires_encryption(self) -> bool:
        """Check if the dataset requires KMS encryption."""
        if self.kms_key_required:
            return True
        if self.jurisdiction and self.jurisdiction.data_residency_required:
            return True
        return any(t.has_pii() for t in self.tables)
