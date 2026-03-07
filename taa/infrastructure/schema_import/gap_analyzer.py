"""Gap analyzer — compares imported schema against canonical model."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import BSSVendor
from taa.infrastructure.schema_import.parser import ImportedTable
from taa.infrastructure.schema_import.mapping_suggester import SuggestedMapping


@dataclass(frozen=True)
class GapReport:
    """Gap analysis result comparing imported schema to canonical model."""

    vendor: BSSVendor | None
    vendor_confidence: float
    imported_tables: int
    imported_columns: int
    canonical_tables: int
    canonical_columns: int
    mapped_columns: int
    suggestions: tuple[SuggestedMapping, ...]
    unmapped_imported: tuple[str, ...]    # vendor fields with no match
    uncovered_canonical: tuple[str, ...]  # canonical fields with no match

    @property
    def mapping_coverage_pct(self) -> float:
        if self.canonical_columns == 0:
            return 100.0
        return (self.mapped_columns / self.canonical_columns) * 100.0

    @property
    def import_coverage_pct(self) -> float:
        if self.imported_columns == 0:
            return 0.0
        return (self.mapped_columns / self.imported_columns) * 100.0

    def to_markdown(self) -> str:
        lines = [
            "# Schema Import Gap Analysis Report",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Detected Vendor | {self.vendor.value if self.vendor else 'Unknown'} (confidence: {self.vendor_confidence:.0%}) |",
            f"| Imported Tables | {self.imported_tables} |",
            f"| Imported Columns | {self.imported_columns} |",
            f"| Canonical Tables | {self.canonical_tables} |",
            f"| Canonical Columns | {self.canonical_columns} |",
            f"| Mapped Columns | {self.mapped_columns} |",
            f"| Canonical Coverage | {self.mapping_coverage_pct:.1f}% |",
            f"| Import Coverage | {self.import_coverage_pct:.1f}% |",
            "",
        ]

        if self.suggestions:
            lines.append("## Suggested Mappings")
            lines.append("")
            lines.append("| Source Table | Source Field | Canonical Table | Canonical Field | Confidence | Reason |")
            lines.append("|-------------|-------------|-----------------|-----------------|------------|--------|")
            for s in sorted(self.suggestions, key=lambda x: -x.confidence):
                lines.append(
                    f"| {s.vendor_table} | {s.vendor_field} | {s.canonical_table} "
                    f"| {s.canonical_field} | {s.confidence:.0%} | {s.match_reason} |"
                )
            lines.append("")

        if self.uncovered_canonical:
            lines.append("## Uncovered Canonical Fields")
            lines.append("")
            lines.append("These canonical fields have no matching imported column:")
            lines.append("")
            for field in self.uncovered_canonical[:50]:  # Limit output
                lines.append(f"- {field}")
            if len(self.uncovered_canonical) > 50:
                lines.append(f"- ... and {len(self.uncovered_canonical) - 50} more")
            lines.append("")

        if self.unmapped_imported:
            lines.append("## Unmapped Imported Fields")
            lines.append("")
            lines.append("These imported fields could not be matched to any canonical field:")
            lines.append("")
            for field in self.unmapped_imported[:50]:
                lines.append(f"- {field}")
            if len(self.unmapped_imported) > 50:
                lines.append(f"- ... and {len(self.unmapped_imported) - 50} more")
            lines.append("")

        return "\n".join(lines)


class GapAnalyzer:
    """Produces a gap analysis report comparing imported schema to canonical model."""

    def analyze(
        self,
        imported_tables: tuple[ImportedTable, ...],
        canonical_tables: tuple[Table, ...],
        suggestions: tuple[SuggestedMapping, ...],
        vendor: BSSVendor | None = None,
        vendor_confidence: float = 0.0,
    ) -> GapReport:
        imported_cols = sum(len(t.columns) for t in imported_tables)
        canonical_cols = sum(len(t.columns) for t in canonical_tables)

        # Build sets for gap identification
        mapped_vendor_fields = {
            f"{s.vendor_table}.{s.vendor_field}" for s in suggestions
        }
        mapped_canonical_fields = {
            f"{s.canonical_table}.{s.canonical_field}" for s in suggestions
        }

        all_imported = {
            f"{t.name}.{c.name}"
            for t in imported_tables
            for c in t.columns
        }
        all_canonical = {
            f"{t.name}.{c.name}"
            for t in canonical_tables
            for c in t.columns
        }

        unmapped_imported = sorted(all_imported - mapped_vendor_fields)
        uncovered_canonical = sorted(all_canonical - mapped_canonical_fields)

        return GapReport(
            vendor=vendor,
            vendor_confidence=vendor_confidence,
            imported_tables=len(imported_tables),
            imported_columns=imported_cols,
            canonical_tables=len(canonical_tables),
            canonical_columns=canonical_cols,
            mapped_columns=len(mapped_canonical_fields & all_canonical),
            suggestions=suggestions,
            unmapped_imported=tuple(unmapped_imported),
            uncovered_canonical=tuple(uncovered_canonical),
        )
