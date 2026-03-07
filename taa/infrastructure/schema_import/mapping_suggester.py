"""Mapping suggester — suggests vendor-to-canonical mappings from imported schema."""

from __future__ import annotations

import re
from dataclasses import dataclass

from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import BSSVendor, TelcoDomain
from taa.infrastructure.schema_import.parser import ImportedTable, ImportedColumn


@dataclass(frozen=True)
class SuggestedMapping:
    """A suggested mapping from an imported column to a canonical column."""

    vendor_table: str
    vendor_field: str
    canonical_table: str
    canonical_field: str
    confidence: float
    match_reason: str


class MappingSuggester:
    """Suggests mappings from imported schema to canonical model using fuzzy matching."""

    def suggest(
        self,
        imported_tables: tuple[ImportedTable, ...],
        canonical_tables: tuple[Table, ...],
        vendor: BSSVendor | None = None,
    ) -> tuple[SuggestedMapping, ...]:
        """Generate mapping suggestions with confidence scores."""
        suggestions: list[SuggestedMapping] = []

        # Build canonical field index: normalized_name → (table, column)
        canonical_index = self._build_canonical_index(canonical_tables)

        for imp_table in imported_tables:
            for imp_col in imp_table.columns:
                best = self._find_best_match(
                    imp_table.name, imp_col, canonical_index, canonical_tables
                )
                if best:
                    suggestions.append(best)

        return tuple(suggestions)

    def _build_canonical_index(
        self, tables: tuple[Table, ...]
    ) -> dict[str, list[tuple[str, str]]]:
        """Build index of normalized canonical field names."""
        index: dict[str, list[tuple[str, str]]] = {}
        for table in tables:
            for col in table.columns:
                normalized = self._normalize(col.name)
                index.setdefault(normalized, []).append((table.name, col.name))
                # Also index without common prefixes/suffixes
                for variant in self._name_variants(col.name):
                    index.setdefault(variant, []).append((table.name, col.name))
        return index

    def _find_best_match(
        self,
        table_name: str,
        col: ImportedColumn,
        index: dict[str, list[tuple[str, str]]],
        canonical_tables: tuple[Table, ...],
    ) -> SuggestedMapping | None:
        normalized = self._normalize(col.name)

        # 1. Exact normalized match
        if normalized in index:
            target = index[normalized][0]
            return SuggestedMapping(
                vendor_table=table_name,
                vendor_field=col.name,
                canonical_table=target[0],
                canonical_field=target[1],
                confidence=0.95,
                match_reason="exact name match",
            )

        # 2. Try variants of the imported column name
        for variant in self._name_variants(col.name):
            if variant in index:
                target = index[variant][0]
                return SuggestedMapping(
                    vendor_table=table_name,
                    vendor_field=col.name,
                    canonical_table=target[0],
                    canonical_field=target[1],
                    confidence=0.85,
                    match_reason="variant name match",
                )

        # 3. Substring/contains match
        for canon_key, targets in index.items():
            if len(canon_key) >= 4 and (
                canon_key in normalized or normalized in canon_key
            ):
                target = targets[0]
                overlap = len(set(canon_key) & set(normalized)) / max(len(canon_key), len(normalized))
                if overlap > 0.5:
                    return SuggestedMapping(
                        vendor_table=table_name,
                        vendor_field=col.name,
                        canonical_table=target[0],
                        canonical_field=target[1],
                        confidence=round(0.6 + overlap * 0.2, 2),
                        match_reason="substring match",
                    )

        return None

    def _normalize(self, name: str) -> str:
        """Normalize a column name for comparison."""
        # Remove common prefixes
        name = re.sub(r"^(col_|fld_|f_|c_)", "", name, flags=re.IGNORECASE)
        # Lowercase, strip underscores
        return name.lower().replace("_", "").replace("-", "")

    def _name_variants(self, name: str) -> list[str]:
        """Generate name variants for fuzzy matching."""
        lower = name.lower()
        variants: list[str] = []

        # Strip vendor prefixes (CM_, CBS_, etc.)
        stripped = re.sub(r"^[a-z]{2,4}_", "", lower)
        if stripped != lower:
            variants.append(stripped.replace("_", ""))

        # Common abbreviation expansions
        expansions = {
            "num": "number", "no": "number", "nbr": "number",
            "dt": "date", "dte": "date",
            "amt": "amount", "amnt": "amount",
            "desc": "description", "descr": "description",
            "addr": "address",
            "tel": "telephone", "ph": "phone",
            "acct": "account", "acc": "account",
            "cust": "customer",
            "sub": "subscriber",
            "stat": "status", "sts": "status",
            "typ": "type",
            "cd": "code",
            "id": "id", "ident": "id",
            "ts": "timestamp", "tmstmp": "timestamp",
            "qty": "quantity",
            "pct": "percentage",
            "curr": "currency",
            "bal": "balance",
        }
        parts = lower.split("_")
        expanded = []
        for part in parts:
            expanded.append(expansions.get(part, part))
        expanded_name = "".join(expanded)
        if expanded_name != lower.replace("_", ""):
            variants.append(expanded_name)

        # Strip _id, _code suffixes and try
        for suffix in ("_id", "_code", "_flag", "_ind", "_type", "_name"):
            if lower.endswith(suffix):
                base = lower[: -len(suffix)].replace("_", "")
                variants.append(base)

        return variants
