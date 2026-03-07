"""Schema migration generator - produces ALTER TABLE DDL for BigQuery schema evolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table


@dataclass(frozen=True)
class ColumnDiff:
    """Represents a single column-level difference between two table versions."""

    table_name: str
    column_name: str
    change_type: str  # "added", "removed", "type_changed"
    old_type: str | None = None
    new_type: str | None = None
    new_column: Column | None = None


@dataclass(frozen=True)
class MigrationPlan:
    """Complete migration plan between two schema versions."""

    from_version: str
    to_version: str
    timestamp: str
    diffs: tuple[ColumnDiff, ...]
    alter_statements: tuple[str, ...]
    view_statements: tuple[str, ...]


class SchemaMigrationGenerator:
    """Generates BigQuery-compatible ALTER TABLE DDL for schema migrations.

    Compares old and new table definitions and produces:
    - ALTER TABLE ... ADD COLUMN for added columns
    - ALTER TABLE ... DROP COLUMN for removed columns
    - Comments for type changes (BigQuery does not support ALTER COLUMN TYPE)
    - Backward-compatible views for old versions
    """

    def __init__(self, project_id: str = "telco-analytics") -> None:
        self._project_id = project_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def diff_tables(
        self,
        old_tables: tuple[Table, ...],
        new_tables: tuple[Table, ...],
    ) -> tuple[ColumnDiff, ...]:
        """Detect column-level differences between two sets of table definitions."""
        diffs: list[ColumnDiff] = []

        old_map = {t.name: t for t in old_tables}
        new_map = {t.name: t for t in new_tables}

        all_table_names = set(old_map.keys()) | set(new_map.keys())

        for table_name in sorted(all_table_names):
            old_table = old_map.get(table_name)
            new_table = new_map.get(table_name)

            if old_table is None and new_table is not None:
                # Entire table is new - every column is "added"
                for col in new_table.columns:
                    diffs.append(ColumnDiff(
                        table_name=table_name,
                        column_name=col.name,
                        change_type="added",
                        new_column=col,
                    ))
                continue

            if new_table is None and old_table is not None:
                # Entire table removed - every column is "removed"
                for col in old_table.columns:
                    diffs.append(ColumnDiff(
                        table_name=table_name,
                        column_name=col.name,
                        change_type="removed",
                    ))
                continue

            # Both exist - compare columns
            assert old_table is not None and new_table is not None
            diffs.extend(self._diff_columns(table_name, old_table, new_table))

        return tuple(diffs)

    def generate(
        self,
        old_tables: tuple[Table, ...],
        new_tables: tuple[Table, ...],
        dataset_name: str,
        from_version: str = "v1",
        to_version: str = "v2",
    ) -> MigrationPlan:
        """Generate a full migration plan including DDL and backward-compatible views."""
        diffs = self.diff_tables(old_tables, new_tables)

        alter_stmts = self._generate_alter_statements(diffs, dataset_name)
        view_stmts = self._generate_backward_views(
            old_tables, new_tables, diffs, dataset_name, from_version,
        )

        return MigrationPlan(
            from_version=from_version,
            to_version=to_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
            diffs=diffs,
            alter_statements=tuple(alter_stmts),
            view_statements=tuple(view_stmts),
        )

    def render_sql(self, plan: MigrationPlan) -> str:
        """Render a MigrationPlan into a single SQL script string."""
        lines: list[str] = [
            f"-- Migration: {plan.from_version} -> {plan.to_version}",
            f"-- Generated: {plan.timestamp}",
            "",
        ]

        if plan.alter_statements:
            lines.append("-- === ALTER TABLE statements ===")
            lines.append("")
            for stmt in plan.alter_statements:
                lines.append(stmt)
                lines.append("")

        if plan.view_statements:
            lines.append("-- === Backward-compatible views ===")
            lines.append("")
            for stmt in plan.view_statements:
                lines.append(stmt)
                lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _diff_columns(
        self, table_name: str, old_table: Table, new_table: Table,
    ) -> list[ColumnDiff]:
        diffs: list[ColumnDiff] = []

        old_cols = {c.name: c for c in old_table.columns}
        new_cols = {c.name: c for c in new_table.columns}

        # Added columns
        for col_name in sorted(set(new_cols.keys()) - set(old_cols.keys())):
            diffs.append(ColumnDiff(
                table_name=table_name,
                column_name=col_name,
                change_type="added",
                new_column=new_cols[col_name],
            ))

        # Removed columns
        for col_name in sorted(set(old_cols.keys()) - set(new_cols.keys())):
            diffs.append(ColumnDiff(
                table_name=table_name,
                column_name=col_name,
                change_type="removed",
            ))

        # Type changes
        for col_name in sorted(set(old_cols.keys()) & set(new_cols.keys())):
            old_col = old_cols[col_name]
            new_col = new_cols[col_name]
            if old_col.bigquery_type != new_col.bigquery_type:
                diffs.append(ColumnDiff(
                    table_name=table_name,
                    column_name=col_name,
                    change_type="type_changed",
                    old_type=old_col.bigquery_type.value,
                    new_type=new_col.bigquery_type.value,
                    new_column=new_col,
                ))

        return diffs

    def _column_ddl_fragment(self, col: Column) -> str:
        """Build the column type + OPTIONS fragment for an ADD COLUMN statement."""
        parts = [col.bigquery_type.value]
        if not col.nullable:
            parts.append("NOT NULL")

        options: list[str] = []
        if col.description:
            escaped = col.description.replace("'", "\\'")
            options.append(f"description='{escaped}'")
        if col.policy_tag:
            options.append(f"policy_tags='{col.policy_tag}'")

        if options:
            parts.append(f"OPTIONS({', '.join(options)})")

        return " ".join(parts)

    def _generate_alter_statements(
        self, diffs: tuple[ColumnDiff, ...], dataset_name: str,
    ) -> list[str]:
        stmts: list[str] = []

        for diff in diffs:
            fq_table = f"{dataset_name}.{diff.table_name}"

            if diff.change_type == "added" and diff.new_column is not None:
                type_fragment = self._column_ddl_fragment(diff.new_column)
                stmts.append(
                    f"ALTER TABLE {fq_table} ADD COLUMN {diff.column_name} {type_fragment};"
                )

            elif diff.change_type == "removed":
                stmts.append(
                    f"ALTER TABLE {fq_table} DROP COLUMN {diff.column_name};"
                )

            elif diff.change_type == "type_changed":
                stmts.append(
                    f"-- WARNING: BigQuery does not support ALTER COLUMN TYPE directly."
                )
                stmts.append(
                    f"-- Column '{diff.column_name}' in '{fq_table}' changed from "
                    f"{diff.old_type} to {diff.new_type}."
                )
                stmts.append(
                    f"-- Consider recreating the table or using CAST in a view."
                )

        return stmts

    def _generate_backward_views(
        self,
        old_tables: tuple[Table, ...],
        new_tables: tuple[Table, ...],
        diffs: tuple[ColumnDiff, ...],
        dataset_name: str,
        old_version: str,
    ) -> list[str]:
        """Generate CREATE OR REPLACE VIEW statements that expose the old schema shape."""
        views: list[str] = []

        old_map = {t.name: t for t in old_tables}
        new_map = {t.name: t for t in new_tables}

        # Tables that changed need a backward-compatible view
        changed_tables = {d.table_name for d in diffs}

        for table_name in sorted(changed_tables):
            old_table = old_map.get(table_name)
            if old_table is None:
                # Table didn't exist in old version - no backward view needed
                continue
            if table_name not in new_map:
                # Table was removed - can't create a view
                continue

            new_table = new_map[table_name]
            old_col_names = [c.name for c in old_table.columns]
            new_col_names = {c.name for c in new_table.columns}

            # Build SELECT list: only columns that existed in old AND still exist in new
            select_cols: list[str] = []
            for col_name in old_col_names:
                if col_name in new_col_names:
                    # Check for type change and CAST if needed
                    old_col = next(c for c in old_table.columns if c.name == col_name)
                    new_col = next(c for c in new_table.columns if c.name == col_name)
                    if old_col.bigquery_type != new_col.bigquery_type:
                        select_cols.append(
                            f"CAST({col_name} AS {old_col.bigquery_type.value}) AS {col_name}"
                        )
                    else:
                        select_cols.append(col_name)
                else:
                    # Column was removed in new version - use NULL placeholder
                    old_col = next(c for c in old_table.columns if c.name == col_name)
                    select_cols.append(
                        f"CAST(NULL AS {old_col.bigquery_type.value}) AS {col_name}"
                    )

            if not select_cols:
                continue

            select_list = ",\n  ".join(select_cols)
            view_name = f"{table_name}_{old_version}"
            view_sql = (
                f"CREATE OR REPLACE VIEW {dataset_name}.{view_name} AS\n"
                f"SELECT\n  {select_list}\n"
                f"FROM {dataset_name}.{table_name};"
            )
            views.append(view_sql)

        return views
