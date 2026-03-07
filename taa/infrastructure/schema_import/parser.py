"""Schema parser — reads DDL or CSV and extracts table/column metadata."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImportedColumn:
    """A column parsed from an external schema."""

    name: str
    data_type: str = "VARCHAR"
    nullable: bool = True


@dataclass(frozen=True)
class ImportedTable:
    """A table parsed from an external schema."""

    name: str
    columns: tuple[ImportedColumn, ...] = ()


class SchemaParser:
    """Parses DDL (CREATE TABLE) statements or CSV schema exports."""

    def parse(self, content: str, fmt: str = "auto") -> tuple[ImportedTable, ...]:
        """Parse schema content. fmt can be 'ddl', 'csv', or 'auto'."""
        if fmt == "auto":
            fmt = self._detect_format(content)
        if fmt == "ddl":
            return self._parse_ddl(content)
        if fmt == "csv":
            return self._parse_csv(content)
        raise ValueError(f"Unknown format: {fmt}")

    def parse_file(self, path: str) -> tuple[ImportedTable, ...]:
        """Parse a schema file, detecting format from extension."""
        with open(path) as f:
            content = f.read()
        if path.endswith(".csv"):
            return self._parse_csv(content)
        return self.parse(content, "auto")

    def _detect_format(self, content: str) -> str:
        if re.search(r"CREATE\s+TABLE", content, re.IGNORECASE):
            return "ddl"
        if "," in content.split("\n")[0] and any(
            kw in content.split("\n")[0].lower()
            for kw in ("table", "column", "field", "name")
        ):
            return "csv"
        # Default to DDL
        return "ddl"

    def _parse_ddl(self, content: str) -> tuple[ImportedTable, ...]:
        tables: list[ImportedTable] = []
        # Match CREATE TABLE statements
        pattern = re.compile(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
            r"[`\"\[]?(\w+(?:\.\w+)*)[`\"\]]?\s*\((.*?)\)\s*;",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(content):
            table_name = match.group(1).split(".")[-1]  # Strip schema prefix
            body = match.group(2)
            columns = self._parse_ddl_columns(body)
            tables.append(ImportedTable(name=table_name, columns=tuple(columns)))
        return tuple(tables)

    def _parse_ddl_columns(self, body: str) -> list[ImportedColumn]:
        columns: list[ImportedColumn] = []
        # Split by comma but respect parentheses (for NUMERIC(10,2) etc.)
        parts: list[str] = []
        depth = 0
        current: list[str] = []
        for char in body:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
                continue
            current.append(char)
        if current:
            parts.append("".join(current).strip())

        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Skip constraints
            upper = part.upper().lstrip()
            if any(upper.startswith(kw) for kw in (
                "PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT",
                "INDEX", "KEY", "PARTITION", "CLUSTER", "OPTIONS",
            )):
                continue

            tokens = part.split()
            if len(tokens) < 2:
                continue

            col_name = tokens[0].strip("`\"[]")
            data_type = tokens[1].strip("`\"[]")
            # Capture type with precision e.g. NUMERIC(10,2)
            if len(tokens) > 2 and tokens[2].startswith("("):
                data_type += tokens[2]
            nullable = "NOT NULL" not in part.upper()
            columns.append(ImportedColumn(
                name=col_name, data_type=data_type.upper(), nullable=nullable,
            ))
        return columns

    def _parse_csv(self, content: str) -> tuple[ImportedTable, ...]:
        reader = csv.DictReader(io.StringIO(content))
        # Normalize header names
        if reader.fieldnames is None:
            return ()

        field_map: dict[str, str] = {}
        for fn in reader.fieldnames:
            lower = fn.lower().strip()
            if "table" in lower:
                field_map["table"] = fn
            elif "column" in lower or "field" in lower:
                field_map["column"] = fn
            elif "type" in lower or "data" in lower:
                field_map["type"] = fn
            elif "null" in lower:
                field_map["nullable"] = fn

        if "table" not in field_map or "column" not in field_map:
            raise ValueError(
                "CSV must have 'table' and 'column'/'field' headers. "
                f"Found: {reader.fieldnames}"
            )

        tables_dict: dict[str, list[ImportedColumn]] = {}
        for row in reader:
            table_name = row[field_map["table"]].strip()
            col_name = row[field_map["column"]].strip()
            data_type = row.get(field_map.get("type", ""), "VARCHAR").strip().upper()
            nullable_str = row.get(field_map.get("nullable", ""), "YES").strip().upper()
            nullable = nullable_str not in ("NO", "FALSE", "0", "NOT NULL")

            tables_dict.setdefault(table_name, []).append(
                ImportedColumn(name=col_name, data_type=data_type or "VARCHAR", nullable=nullable)
            )

        return tuple(
            ImportedTable(name=name, columns=tuple(cols))
            for name, cols in tables_dict.items()
        )
