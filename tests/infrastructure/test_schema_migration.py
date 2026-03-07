"""Tests for the SchemaMigrationGenerator."""

import pytest

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import BigQueryType, TelcoDomain, PIICategory
from taa.infrastructure.generators.schema_migration import (
    SchemaMigrationGenerator,
    ColumnDiff,
    MigrationPlan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gen():
    return SchemaMigrationGenerator()


@pytest.fixture
def old_table():
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
            Column(name="legacy_field", bigquery_type=BigQueryType.STRING),
        ),
        dataset_name="subscriber_ds",
    )


@pytest.fixture
def new_table():
    return Table(
        name="subscriber_profile",
        telco_domain=TelcoDomain.SUBSCRIBER,
        columns=(
            Column(name="subscriber_id", bigquery_type=BigQueryType.STRING, nullable=False,
                   description="Unique subscriber ID"),
            Column(name="msisdn", bigquery_type=BigQueryType.STRING,
                   pii_category=PIICategory.MSISDN),
            Column(name="status", bigquery_type=BigQueryType.INT64),  # type changed
            Column(name="activation_date", bigquery_type=BigQueryType.DATE, nullable=False),
            # legacy_field removed
            Column(name="email", bigquery_type=BigQueryType.STRING,  # added
                   pii_category=PIICategory.EMAIL,
                   description="Contact email"),
        ),
        dataset_name="subscriber_ds",
    )


# ---------------------------------------------------------------------------
# diff_tables tests
# ---------------------------------------------------------------------------

class TestDiffTables:
    def test_detect_added_column(self, gen, old_table, new_table):
        diffs = gen.diff_tables((old_table,), (new_table,))
        added = [d for d in diffs if d.change_type == "added"]
        assert any(d.column_name == "email" for d in added)

    def test_detect_removed_column(self, gen, old_table, new_table):
        diffs = gen.diff_tables((old_table,), (new_table,))
        removed = [d for d in diffs if d.change_type == "removed"]
        assert any(d.column_name == "legacy_field" for d in removed)

    def test_detect_type_change(self, gen, old_table, new_table):
        diffs = gen.diff_tables((old_table,), (new_table,))
        changed = [d for d in diffs if d.change_type == "type_changed"]
        assert len(changed) == 1
        assert changed[0].column_name == "status"
        assert changed[0].old_type == "STRING"
        assert changed[0].new_type == "INT64"

    def test_no_diff_for_identical_tables(self, gen, old_table):
        diffs = gen.diff_tables((old_table,), (old_table,))
        assert len(diffs) == 0

    def test_entirely_new_table(self, gen):
        new = Table(
            name="new_table",
            telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(
                Column(name="id", bigquery_type=BigQueryType.STRING, nullable=False),
                Column(name="value", bigquery_type=BigQueryType.INT64),
            ),
        )
        diffs = gen.diff_tables((), (new,))
        assert len(diffs) == 2
        assert all(d.change_type == "added" for d in diffs)

    def test_entirely_removed_table(self, gen, old_table):
        diffs = gen.diff_tables((old_table,), ())
        assert len(diffs) == len(old_table.columns)
        assert all(d.change_type == "removed" for d in diffs)


# ---------------------------------------------------------------------------
# generate tests
# ---------------------------------------------------------------------------

class TestGenerate:
    def test_returns_migration_plan(self, gen, old_table, new_table):
        plan = gen.generate(
            (old_table,), (new_table,), "subscriber_ds",
            from_version="v1", to_version="v2",
        )
        assert isinstance(plan, MigrationPlan)
        assert plan.from_version == "v1"
        assert plan.to_version == "v2"
        assert len(plan.diffs) > 0

    def test_alter_add_column(self, gen, old_table, new_table):
        plan = gen.generate((old_table,), (new_table,), "subscriber_ds")
        add_stmts = [s for s in plan.alter_statements if "ADD COLUMN" in s]
        assert any("email" in s for s in add_stmts)
        # Should include type
        assert any("STRING" in s for s in add_stmts)

    def test_alter_drop_column(self, gen, old_table, new_table):
        plan = gen.generate((old_table,), (new_table,), "subscriber_ds")
        drop_stmts = [s for s in plan.alter_statements if "DROP COLUMN" in s]
        assert any("legacy_field" in s for s in drop_stmts)

    def test_alter_type_change_comment(self, gen, old_table, new_table):
        plan = gen.generate((old_table,), (new_table,), "subscriber_ds")
        comments = [s for s in plan.alter_statements if s.startswith("--")]
        assert any("status" in c for c in comments)
        assert any("ALTER COLUMN TYPE" in c for c in comments)

    def test_add_column_with_options(self, gen):
        old = Table(
            name="t", telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(Column(name="id", bigquery_type=BigQueryType.STRING, nullable=False),),
        )
        new = Table(
            name="t", telco_domain=TelcoDomain.SUBSCRIBER,
            columns=(
                Column(name="id", bigquery_type=BigQueryType.STRING, nullable=False),
                Column(name="desc_col", bigquery_type=BigQueryType.STRING,
                       description="A description"),
            ),
        )
        plan = gen.generate((old,), (new,), "ds")
        add_stmts = [s for s in plan.alter_statements if "ADD COLUMN" in s]
        assert any("OPTIONS" in s and "description=" in s for s in add_stmts)


# ---------------------------------------------------------------------------
# Backward-compatible views
# ---------------------------------------------------------------------------

class TestBackwardViews:
    def test_view_generated_for_changed_table(self, gen, old_table, new_table):
        plan = gen.generate(
            (old_table,), (new_table,), "subscriber_ds",
            from_version="v1", to_version="v2",
        )
        assert len(plan.view_statements) > 0
        view_sql = plan.view_statements[0]
        assert "CREATE OR REPLACE VIEW" in view_sql
        assert "subscriber_profile_v1" in view_sql

    def test_view_contains_old_columns(self, gen, old_table, new_table):
        plan = gen.generate(
            (old_table,), (new_table,), "subscriber_ds",
            from_version="v1", to_version="v2",
        )
        view_sql = plan.view_statements[0]
        # Old columns that still exist should be selected
        assert "subscriber_id" in view_sql
        assert "msisdn" in view_sql
        # Removed column should appear as CAST(NULL ...)
        assert "legacy_field" in view_sql
        assert "NULL" in view_sql

    def test_view_casts_type_changes(self, gen, old_table, new_table):
        plan = gen.generate(
            (old_table,), (new_table,), "subscriber_ds",
            from_version="v1", to_version="v2",
        )
        view_sql = plan.view_statements[0]
        # status changed from STRING to INT64, view should CAST back to STRING
        assert "CAST(status AS STRING)" in view_sql

    def test_no_view_for_unchanged_table(self, gen, old_table):
        plan = gen.generate(
            (old_table,), (old_table,), "subscriber_ds",
        )
        assert len(plan.view_statements) == 0


# ---------------------------------------------------------------------------
# render_sql
# ---------------------------------------------------------------------------

class TestRenderSQL:
    def test_render_contains_header(self, gen, old_table, new_table):
        plan = gen.generate(
            (old_table,), (new_table,), "subscriber_ds",
            from_version="v1", to_version="v2",
        )
        sql = gen.render_sql(plan)
        assert "Migration: v1 -> v2" in sql
        assert "ALTER TABLE" in sql

    def test_render_contains_views(self, gen, old_table, new_table):
        plan = gen.generate(
            (old_table,), (new_table,), "subscriber_ds",
            from_version="v1", to_version="v2",
        )
        sql = gen.render_sql(plan)
        assert "Backward-compatible views" in sql
        assert "CREATE OR REPLACE VIEW" in sql

    def test_empty_migration(self, gen, old_table):
        plan = gen.generate((old_table,), (old_table,), "subscriber_ds")
        sql = gen.render_sql(plan)
        assert "Migration:" in sql
        # No ALTER or VIEW statements
        assert "ALTER TABLE" not in sql
        assert "CREATE OR REPLACE VIEW" not in sql
