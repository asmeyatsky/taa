"""PII detection domain service."""

from __future__ import annotations

import re

from taa.domain.entities.column import Column
from taa.domain.value_objects.enums import PIICategory, BigQueryType

# Pattern-based PII classification rules
_PII_PATTERNS: dict[PIICategory, list[str]] = {
    PIICategory.MSISDN: [r"msisdn", r"phone.*num", r"mobile.*num", r"calling.*num", r"called.*num"],
    PIICategory.IMSI: [r"imsi", r"subscriber.*identity"],
    PIICategory.IMEI: [r"imei", r"device.*id", r"terminal.*id"],
    PIICategory.EMAIL: [r"email", r"e_mail"],
    PIICategory.NATIONAL_ID: [r"national.*id", r"passport", r"civil.*id", r"iqama", r"emirates.*id"],
    PIICategory.NAME: [r"first.*name", r"last.*name", r"full.*name", r"customer.*name", r"subscriber.*name"],
    PIICategory.IP_ADDRESS: [r"ip.*addr", r"source.*ip", r"dest.*ip", r"client.*ip"],
    PIICategory.ADDRESS: [r"(?<!\bip.)address", r"street", r"city", r"postal.*code", r"zip.*code"],
    PIICategory.DATE_OF_BIRTH: [r"date.*birth", r"dob", r"birth.*date"],
    PIICategory.LOCATION: [r"latitude", r"longitude", r"cell.*id", r"lac", r"location.*area"],
}

_COMPILED_PATTERNS: dict[PIICategory, list[re.Pattern[str]]] = {
    category: [re.compile(p, re.IGNORECASE) for p in patterns]
    for category, patterns in _PII_PATTERNS.items()
}


class PIIDetectionService:
    """Classifies columns by name pattern matching against PII categories."""

    def classify_column(self, column_name: str) -> PIICategory | None:
        """Classify a column name into a PII category, or None if not PII."""
        for category, patterns in _COMPILED_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(column_name):
                    return category
        return None

    def scan_columns(self, columns: tuple[Column, ...]) -> list[tuple[Column, PIICategory]]:
        """Scan columns and return those detected as PII with their category."""
        results: list[tuple[Column, PIICategory]] = []
        for col in columns:
            if col.pii_category is not None:
                results.append((col, col.pii_category))
            else:
                detected = self.classify_column(col.name)
                if detected is not None:
                    results.append((col, detected))
        return results

    def enrich_column(self, column: Column) -> Column:
        """Return a new Column with PII metadata if PII is detected."""
        if column.pii_category is not None:
            return column
        detected = self.classify_column(column.name)
        if detected is None:
            return column
        return Column(
            name=column.name,
            bigquery_type=column.bigquery_type,
            description=column.description,
            nullable=column.nullable,
            pii_category=detected,
            policy_tag=f"projects/telco/locations/global/taxonomies/pii/policyTags/{detected.value}",
            masking_pattern="HASH",
        )

    def enrich_columns(self, columns: tuple[Column, ...]) -> tuple[Column, ...]:
        """Return enriched columns with PII metadata applied."""
        return tuple(self.enrich_column(c) for c in columns)
