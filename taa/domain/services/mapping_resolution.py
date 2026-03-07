"""Mapping resolution domain service."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.entities.vendor_mapping import VendorMapping
from taa.domain.entities.table import Table


@dataclass(frozen=True)
class MappingCoverage:
    """Result of mapping coverage analysis."""

    total_canonical_fields: int
    mapped_fields: int
    unmapped_fields: tuple[str, ...]
    conflicts: tuple[MappingConflict, ...]

    @property
    def coverage_pct(self) -> float:
        if self.total_canonical_fields == 0:
            return 100.0
        return (self.mapped_fields / self.total_canonical_fields) * 100.0


@dataclass(frozen=True)
class MappingConflict:
    """A conflict where multiple vendor fields map to the same canonical field."""

    canonical_table: str
    canonical_field: str
    conflicting_mappings: tuple[VendorMapping, ...]


class MappingResolutionService:
    """Resolves vendor-to-canonical mappings and detects conflicts."""

    def resolve(
        self,
        mappings: tuple[VendorMapping, ...],
        canonical_tables: tuple[Table, ...],
    ) -> MappingCoverage:
        """Resolve mappings against canonical tables and calculate coverage."""
        # Build set of all canonical fields
        all_fields: set[str] = set()
        for table in canonical_tables:
            for col in table.columns:
                all_fields.add(f"{table.name}.{col.name}")

        # Build mapped fields set and detect conflicts
        field_mappings: dict[str, list[VendorMapping]] = {}
        for mapping in mappings:
            key = f"{mapping.canonical_table}.{mapping.canonical_field}"
            field_mappings.setdefault(key, []).append(mapping)

        mapped = set(field_mappings.keys()) & all_fields
        unmapped = all_fields - set(field_mappings.keys())

        # Detect conflicts
        conflicts: list[MappingConflict] = []
        for key, maps in field_mappings.items():
            if len(maps) > 1:
                parts = key.split(".", 1)
                conflicts.append(MappingConflict(
                    canonical_table=parts[0],
                    canonical_field=parts[1] if len(parts) > 1 else "",
                    conflicting_mappings=tuple(maps),
                ))

        return MappingCoverage(
            total_canonical_fields=len(all_fields),
            mapped_fields=len(mapped),
            unmapped_fields=tuple(sorted(unmapped)),
            conflicts=tuple(conflicts),
        )

    def filter_by_confidence(
        self,
        mappings: tuple[VendorMapping, ...],
        min_confidence: float = 0.8,
    ) -> tuple[VendorMapping, ...]:
        """Filter mappings by minimum confidence threshold."""
        return tuple(m for m in mappings if m.confidence >= min_confidence)
