"""Data quality rule generator - produces BigQuery SQL assertions for data quality checks."""

from __future__ import annotations

from dataclasses import dataclass

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import BigQueryType


# Types considered numeric for range checks
_NUMERIC_TYPES = frozenset({
    BigQueryType.INT64,
    BigQueryType.FLOAT64,
    BigQueryType.NUMERIC,
    BigQueryType.BIGNUMERIC,
})

# Types considered date/timestamp for freshness and range checks
_TEMPORAL_TYPES = frozenset({
    BigQueryType.DATE,
    BigQueryType.DATETIME,
    BigQueryType.TIMESTAMP,
})

# Column name fragments that indicate monetary amounts (should be >= 0)
_AMOUNT_KEYWORDS = ("amount", "charge", "fee", "cost", "revenue", "balance", "price")

# Column name fragments that indicate durations (should be >= 0)
_DURATION_KEYWORDS = ("duration", "seconds", "minutes", "hours", "days", "count")

# Well-known date pairs where the first should be <= the second
_DATE_ORDER_PAIRS = (
    ("activation_date", "deactivation_date"),
    ("start_date", "end_date"),
    ("created_at", "updated_at"),
    ("valid_from", "valid_to"),
    ("effective_start", "effective_end"),
)


@dataclass(frozen=True)
class QualityRule:
    """A single data quality rule."""

    rule_id: str
    table_name: str
    rule_type: str
    description: str
    sql: str


class DataQualityGenerator:
    """Generates data quality SQL assertions from Table entities.

    Rule categories:
    - NOT NULL checks for non-nullable columns
    - Valid status value checks (columns containing "status")
    - Referential integrity expectations (columns ending with _id)
    - Date range checks (activation_date < deactivation_date)
    - Numeric range checks (amount >= 0, duration >= 0)
    - Data freshness SLA checks (latest record within last N hours)
    """

    def __init__(
        self,
        dataset_name: str | None = None,
        freshness_hours: int = 24,
    ) -> None:
        self._dataset_name = dataset_name
        self._freshness_hours = freshness_hours

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, tables: tuple[Table, ...]) -> tuple[QualityRule, ...]:
        """Generate all quality rules for the given tables."""
        rules: list[QualityRule] = []
        for table in tables:
            ds = self._resolve_dataset(table)
            rules.extend(self._rules_for_table(table, ds))
        return tuple(rules)

    def generate_sql(self, tables: tuple[Table, ...]) -> str:
        """Generate a single SQL script containing all quality assertions."""
        rules = self.generate(tables)
        return self.render_sql(rules)

    def render_sql(self, rules: tuple[QualityRule, ...]) -> str:
        """Render a collection of QualityRules into a SQL script."""
        lines: list[str] = [
            "-- Data Quality Assertions",
            f"-- Generated rules: {len(rules)}",
            "",
        ]
        for rule in rules:
            lines.append(f"-- [{rule.rule_id}] {rule.description}")
            lines.append(rule.sql)
            lines.append("")
        return "\n".join(lines)

    def generate_airflow_tasks(self, tables: tuple[Table, ...]) -> str:
        """Generate Airflow task definitions for data quality checks.

        Returns Python source code for BigQueryCheckOperator tasks that can be
        integrated into an Airflow DAG.
        """
        rules = self.generate(tables)
        if not rules:
            return "# No data quality rules generated."

        lines: list[str] = [
            "# Data quality check tasks (integrate into your Airflow DAG)",
            "from airflow.providers.google.cloud.operators.bigquery import BigQueryCheckOperator",
            "",
        ]

        for rule in rules:
            task_id = f"dq_{rule.rule_id}".replace("-", "_").lower()
            # Escape the SQL for embedding in a Python string
            escaped_sql = rule.sql.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
            lines.append(
                f"{task_id} = BigQueryCheckOperator(\n"
                f"    task_id='{task_id}',\n"
                f"    sql='{escaped_sql}',\n"
                f"    use_legacy_sql=False,\n"
                f")"
            )
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_dataset(self, table: Table) -> str:
        if self._dataset_name:
            return self._dataset_name
        if table.dataset_name:
            return table.dataset_name
        return f"{table.telco_domain.value}_ds"

    def _fq(self, dataset: str, table_name: str) -> str:
        return f"{dataset}.{table_name}"

    def _rules_for_table(self, table: Table, dataset: str) -> list[QualityRule]:
        rules: list[QualityRule] = []
        fq = self._fq(dataset, table.name)
        col_map = {c.name: c for c in table.columns}

        counter = 0

        def _next_id() -> str:
            nonlocal counter
            counter += 1
            return f"{table.name}-{counter:03d}"

        # 1. NOT NULL checks
        for col in table.columns:
            if not col.nullable:
                rule_id = _next_id()
                rules.append(QualityRule(
                    rule_id=rule_id,
                    table_name=table.name,
                    rule_type="not_null",
                    description=f"{col.name} must not be NULL",
                    sql=(
                        f"SELECT COUNT(*) = 0 FROM {fq} "
                        f"WHERE {col.name} IS NULL;"
                    ),
                ))

        # 2. Status value checks
        for col in table.columns:
            if "status" in col.name.lower() and col.bigquery_type == BigQueryType.STRING:
                rule_id = _next_id()
                rules.append(QualityRule(
                    rule_id=rule_id,
                    table_name=table.name,
                    rule_type="valid_status",
                    description=f"{col.name} must contain valid status values",
                    sql=(
                        f"SELECT COUNT(*) = 0 FROM {fq} "
                        f"WHERE {col.name} IS NOT NULL "
                        f"AND TRIM({col.name}) = '';"
                    ),
                ))

        # 3. Referential integrity (columns ending with _id)
        for col in table.columns:
            if col.name.endswith("_id") and col.bigquery_type == BigQueryType.STRING:
                rule_id = _next_id()
                # Infer the referenced table name from the column name
                # e.g., subscriber_id -> subscriber_profile, plan_id -> plan
                ref_base = col.name[:-3]  # strip _id
                rules.append(QualityRule(
                    rule_id=rule_id,
                    table_name=table.name,
                    rule_type="referential_integrity",
                    description=f"{col.name} should reference a valid entity",
                    sql=(
                        f"-- Referential integrity: ensure {col.name} values exist "
                        f"in the referenced table.\n"
                        f"-- UPDATE the FROM clause to point to the actual reference table.\n"
                        f"SELECT COUNT(*) = 0 FROM {fq} t\n"
                        f"WHERE t.{col.name} IS NOT NULL\n"
                        f"AND NOT EXISTS (\n"
                        f"  SELECT 1 FROM {dataset}.{ref_base} r "
                        f"WHERE r.{col.name} = t.{col.name}\n"
                        f");"
                    ),
                ))

        # 4. Date range checks
        for earlier, later in _DATE_ORDER_PAIRS:
            if earlier in col_map and later in col_map:
                rule_id = _next_id()
                rules.append(QualityRule(
                    rule_id=rule_id,
                    table_name=table.name,
                    rule_type="date_range",
                    description=f"{earlier} must be <= {later}",
                    sql=(
                        f"SELECT COUNT(*) = 0 FROM {fq} "
                        f"WHERE {earlier} IS NOT NULL "
                        f"AND {later} IS NOT NULL "
                        f"AND {earlier} > {later};"
                    ),
                ))

        # 5. Numeric range checks (amounts and durations should be >= 0)
        for col in table.columns:
            if col.bigquery_type not in _NUMERIC_TYPES:
                continue
            col_lower = col.name.lower()
            is_amount = any(kw in col_lower for kw in _AMOUNT_KEYWORDS)
            is_duration = any(kw in col_lower for kw in _DURATION_KEYWORDS)
            if is_amount or is_duration:
                category = "amount" if is_amount else "duration"
                rule_id = _next_id()
                rules.append(QualityRule(
                    rule_id=rule_id,
                    table_name=table.name,
                    rule_type="numeric_range",
                    description=f"{col.name} ({category}) must be >= 0",
                    sql=(
                        f"SELECT COUNT(*) = 0 FROM {fq} "
                        f"WHERE {col.name} IS NOT NULL "
                        f"AND {col.name} < 0;"
                    ),
                ))

        # 6. Data freshness SLA
        temporal_cols = [
            c for c in table.columns if c.bigquery_type in _TEMPORAL_TYPES
        ]
        if temporal_cols:
            # Use the first temporal column (prefer timestamp > datetime > date)
            ts_col = sorted(
                temporal_cols,
                key=lambda c: (
                    0 if c.bigquery_type == BigQueryType.TIMESTAMP
                    else 1 if c.bigquery_type == BigQueryType.DATETIME
                    else 2
                ),
            )[0]
            rule_id = _next_id()
            rules.append(QualityRule(
                rule_id=rule_id,
                table_name=table.name,
                rule_type="freshness",
                description=(
                    f"Table must have data within the last {self._freshness_hours} hours "
                    f"(checked via {ts_col.name})"
                ),
                sql=(
                    f"SELECT COUNT(*) > 0 FROM {fq} "
                    f"WHERE {ts_col.name} >= "
                    f"TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {self._freshness_hours} HOUR);"
                ),
            ))

        return rules
