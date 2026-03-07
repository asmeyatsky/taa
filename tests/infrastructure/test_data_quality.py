"""Tests for the DataQualityGenerator."""

import pytest

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import BigQueryType, TelcoDomain, PIICategory
from taa.infrastructure.generators.data_quality import (
    DataQualityGenerator,
    QualityRule,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def subscriber_table():
    return Table(
        name="subscriber_profile",
        telco_domain=TelcoDomain.SUBSCRIBER,
        columns=(
            Column(name="subscriber_id", bigquery_type=BigQueryType.STRING, nullable=False,
                   description="Unique subscriber ID"),
            Column(name="msisdn", bigquery_type=BigQueryType.STRING,
                   pii_category=PIICategory.MSISDN),
            Column(name="status", bigquery_type=BigQueryType.STRING),
            Column(name="activation_date", bigquery_type=BigQueryType.DATE, nullable=False),
            Column(name="deactivation_date", bigquery_type=BigQueryType.DATE),
            Column(name="plan_id", bigquery_type=BigQueryType.STRING),
            Column(name="monthly_amount", bigquery_type=BigQueryType.NUMERIC),
            Column(name="call_duration", bigquery_type=BigQueryType.INT64),
            Column(name="last_updated", bigquery_type=BigQueryType.TIMESTAMP),
        ),
        dataset_name="subscriber_ds",
    )


@pytest.fixture
def minimal_table():
    return Table(
        name="simple_table",
        telco_domain=TelcoDomain.SUBSCRIBER,
        columns=(
            Column(name="id", bigquery_type=BigQueryType.STRING, nullable=False),
            Column(name="value", bigquery_type=BigQueryType.STRING),
        ),
    )


@pytest.fixture
def gen():
    return DataQualityGenerator()


# ---------------------------------------------------------------------------
# NOT NULL checks
# ---------------------------------------------------------------------------

class TestNotNullChecks:
    def test_generates_not_null_rules(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        nn_rules = [r for r in rules if r.rule_type == "not_null"]
        # subscriber_id and activation_date are NOT NULL
        assert len(nn_rules) == 2
        names = {r.description.split()[0] for r in nn_rules}
        assert "subscriber_id" in names
        assert "activation_date" in names

    def test_not_null_sql(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        nn_rules = [r for r in rules if r.rule_type == "not_null"]
        for rule in nn_rules:
            assert "IS NULL" in rule.sql
            assert "COUNT(*) = 0" in rule.sql

    def test_no_not_null_for_nullable_columns(self, gen, minimal_table):
        rules = gen.generate((minimal_table,))
        nn_rules = [r for r in rules if r.rule_type == "not_null"]
        # Only "id" is non-nullable
        assert len(nn_rules) == 1
        assert "id" in nn_rules[0].description


# ---------------------------------------------------------------------------
# Status value checks
# ---------------------------------------------------------------------------

class TestStatusChecks:
    def test_generates_status_rule(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        status_rules = [r for r in rules if r.rule_type == "valid_status"]
        assert len(status_rules) == 1
        assert "status" in status_rules[0].description

    def test_status_sql_checks_empty(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        status_rules = [r for r in rules if r.rule_type == "valid_status"]
        assert "TRIM" in status_rules[0].sql

    def test_no_status_for_non_string(self, gen):
        table = Table(
            name="t", telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(
                Column(name="status_code", bigquery_type=BigQueryType.INT64),
            ),
        )
        rules = gen.generate((table,))
        status_rules = [r for r in rules if r.rule_type == "valid_status"]
        assert len(status_rules) == 0


# ---------------------------------------------------------------------------
# Referential integrity
# ---------------------------------------------------------------------------

class TestReferentialIntegrity:
    def test_generates_ref_integrity_rule(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        ref_rules = [r for r in rules if r.rule_type == "referential_integrity"]
        assert len(ref_rules) >= 1
        plan_rule = [r for r in ref_rules if "plan_id" in r.description]
        assert len(plan_rule) == 1

    def test_ref_integrity_sql_has_exists(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        ref_rules = [r for r in rules if r.rule_type == "referential_integrity"]
        for rule in ref_rules:
            assert "EXISTS" in rule.sql

    def test_ref_integrity_infers_table_name(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        ref_rules = [r for r in rules if r.rule_type == "referential_integrity"]
        plan_rule = next(r for r in ref_rules if "plan_id" in r.description)
        # Should reference subscriber_ds.plan
        assert "subscriber_ds.plan" in plan_rule.sql


# ---------------------------------------------------------------------------
# Date range checks
# ---------------------------------------------------------------------------

class TestDateRangeChecks:
    def test_generates_date_range_rule(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        date_rules = [r for r in rules if r.rule_type == "date_range"]
        assert len(date_rules) == 1
        assert "activation_date" in date_rules[0].description
        assert "deactivation_date" in date_rules[0].description

    def test_date_range_sql(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        date_rules = [r for r in rules if r.rule_type == "date_range"]
        sql = date_rules[0].sql
        assert "activation_date > deactivation_date" in sql
        assert "COUNT(*) = 0" in sql

    def test_no_date_range_without_pair(self, gen, minimal_table):
        rules = gen.generate((minimal_table,))
        date_rules = [r for r in rules if r.rule_type == "date_range"]
        assert len(date_rules) == 0


# ---------------------------------------------------------------------------
# Numeric range checks
# ---------------------------------------------------------------------------

class TestNumericRangeChecks:
    def test_generates_amount_rule(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        num_rules = [r for r in rules if r.rule_type == "numeric_range"]
        amount_rules = [r for r in num_rules if "amount" in r.description]
        assert len(amount_rules) == 1
        assert "monthly_amount" in amount_rules[0].description

    def test_generates_duration_rule(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        num_rules = [r for r in rules if r.rule_type == "numeric_range"]
        dur_rules = [r for r in num_rules if "duration" in r.description]
        assert len(dur_rules) == 1
        assert "call_duration" in dur_rules[0].description

    def test_numeric_range_sql(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        num_rules = [r for r in rules if r.rule_type == "numeric_range"]
        for rule in num_rules:
            assert "< 0" in rule.sql
            assert "COUNT(*) = 0" in rule.sql

    def test_no_range_for_string_columns(self, gen, minimal_table):
        rules = gen.generate((minimal_table,))
        num_rules = [r for r in rules if r.rule_type == "numeric_range"]
        assert len(num_rules) == 0


# ---------------------------------------------------------------------------
# Freshness SLA checks
# ---------------------------------------------------------------------------

class TestFreshnessChecks:
    def test_generates_freshness_rule(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        fresh_rules = [r for r in rules if r.rule_type == "freshness"]
        assert len(fresh_rules) == 1
        assert "24 hours" in fresh_rules[0].description

    def test_freshness_prefers_timestamp(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        fresh_rules = [r for r in rules if r.rule_type == "freshness"]
        # last_updated (TIMESTAMP) should be preferred over activation_date (DATE)
        assert "last_updated" in fresh_rules[0].sql

    def test_freshness_custom_hours(self, subscriber_table):
        gen = DataQualityGenerator(freshness_hours=6)
        rules = gen.generate((subscriber_table,))
        fresh_rules = [r for r in rules if r.rule_type == "freshness"]
        assert "6 hours" in fresh_rules[0].description
        assert "INTERVAL 6 HOUR" in fresh_rules[0].sql

    def test_freshness_sql(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        fresh_rules = [r for r in rules if r.rule_type == "freshness"]
        sql = fresh_rules[0].sql
        assert "TIMESTAMP_SUB" in sql
        assert "COUNT(*) > 0" in sql

    def test_no_freshness_without_temporal(self, gen, minimal_table):
        rules = gen.generate((minimal_table,))
        fresh_rules = [r for r in rules if r.rule_type == "freshness"]
        assert len(fresh_rules) == 0


# ---------------------------------------------------------------------------
# render_sql
# ---------------------------------------------------------------------------

class TestRenderSQL:
    def test_render_contains_header(self, gen, subscriber_table):
        sql = gen.generate_sql((subscriber_table,))
        assert "Data Quality Assertions" in sql
        assert "Generated rules:" in sql

    def test_render_contains_all_rules(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        sql = gen.generate_sql((subscriber_table,))
        for rule in rules:
            assert rule.rule_id in sql

    def test_render_empty(self, gen):
        table = Table(
            name="empty", telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(Column(name="x", bigquery_type=BigQueryType.STRING),),
        )
        sql = gen.generate_sql((table,))
        assert "Generated rules: 0" in sql


# ---------------------------------------------------------------------------
# generate_airflow_tasks
# ---------------------------------------------------------------------------

class TestAirflowTasks:
    def test_generates_airflow_code(self, gen, subscriber_table):
        code = gen.generate_airflow_tasks((subscriber_table,))
        assert "BigQueryCheckOperator" in code
        assert "task_id=" in code

    def test_generates_one_task_per_rule(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        code = gen.generate_airflow_tasks((subscriber_table,))
        # Each rule should produce a task
        for rule in rules:
            task_id = f"dq_{rule.rule_id}".replace("-", "_").lower()
            assert task_id in code

    def test_no_tasks_for_empty(self, gen):
        table = Table(
            name="empty", telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(Column(name="x", bigquery_type=BigQueryType.STRING),),
        )
        code = gen.generate_airflow_tasks((table,))
        assert "No data quality rules generated" in code


# ---------------------------------------------------------------------------
# Dataset resolution
# ---------------------------------------------------------------------------

class TestDatasetResolution:
    def test_uses_explicit_dataset(self, subscriber_table):
        gen = DataQualityGenerator(dataset_name="custom_ds")
        rules = gen.generate((subscriber_table,))
        for rule in rules:
            assert "custom_ds." in rule.sql

    def test_uses_table_dataset(self, gen, subscriber_table):
        rules = gen.generate((subscriber_table,))
        for rule in rules:
            assert "subscriber_ds." in rule.sql

    def test_falls_back_to_domain(self, gen):
        table = Table(
            name="t", telco_domain=TelcoDomain.CDR_EVENT,
            columns=(Column(name="id", bigquery_type=BigQueryType.STRING, nullable=False),),
        )
        rules = gen.generate((table,))
        assert any("cdr_event_ds." in r.sql for r in rules)


# ---------------------------------------------------------------------------
# Multiple tables
# ---------------------------------------------------------------------------

class TestMultipleTables:
    def test_generates_rules_for_all_tables(self, gen, subscriber_table, minimal_table):
        rules = gen.generate((subscriber_table, minimal_table))
        tables_covered = {r.table_name for r in rules}
        assert "subscriber_profile" in tables_covered
        assert "simple_table" in tables_covered
