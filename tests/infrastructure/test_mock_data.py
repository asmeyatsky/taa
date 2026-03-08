"""Tests for mock data generator."""

from __future__ import annotations

import csv
import io
import json

import pytest

from taa.domain.entities.column import Column
from taa.domain.entities.table import Table
from taa.domain.value_objects.enums import BigQueryType, PIICategory, TelcoDomain
from taa.infrastructure.generators.mock_data import MockDataGenerator


@pytest.fixture()
def sample_table() -> Table:
    return Table(
        name="subscriber_profile",
        telco_domain=TelcoDomain.SUBSCRIBER,
        columns=(
            Column(name="subscriber_id", bigquery_type=BigQueryType.STRING, nullable=False),
            Column(name="msisdn", bigquery_type=BigQueryType.STRING, pii_category=PIICategory.MSISDN),
            Column(name="full_name", bigquery_type=BigQueryType.STRING, pii_category=PIICategory.NAME),
            Column(name="email", bigquery_type=BigQueryType.STRING, pii_category=PIICategory.EMAIL),
            Column(name="status", bigquery_type=BigQueryType.STRING),
            Column(name="activation_date", bigquery_type=BigQueryType.DATE),
            Column(name="churn_risk_score", bigquery_type=BigQueryType.FLOAT64),
            Column(name="is_prepaid", bigquery_type=BigQueryType.BOOLEAN),
            Column(name="total_calls", bigquery_type=BigQueryType.INT64),
            Column(name="last_event", bigquery_type=BigQueryType.TIMESTAMP),
        ),
    )


@pytest.fixture()
def generator() -> MockDataGenerator:
    return MockDataGenerator(seed=42)


class TestGenerateRows:
    def test_returns_correct_count(self, generator, sample_table):
        rows = generator.generate_rows(sample_table, 50)
        assert len(rows) == 50

    def test_rows_have_all_columns(self, generator, sample_table):
        rows = generator.generate_rows(sample_table, 10)
        expected_keys = {c.name for c in sample_table.columns}
        for row in rows:
            assert set(row.keys()) == expected_keys

    def test_msisdn_format(self, generator, sample_table):
        rows = generator.generate_rows(sample_table, 20)
        for row in rows:
            if row["msisdn"] is not None:
                assert row["msisdn"].startswith("+")

    def test_email_format(self, generator, sample_table):
        rows = generator.generate_rows(sample_table, 20)
        for row in rows:
            if row["email"] is not None:
                assert "@" in row["email"]

    def test_status_values(self, generator, sample_table):
        rows = generator.generate_rows(sample_table, 100)
        valid = {"active", "inactive", "suspended", "pending", "terminated"}
        for row in rows:
            if row["status"] is not None:
                assert row["status"] in valid

    def test_boolean_values(self, generator, sample_table):
        rows = generator.generate_rows(sample_table, 20)
        for row in rows:
            if row["is_prepaid"] is not None:
                assert isinstance(row["is_prepaid"], bool)

    def test_seed_reproducibility(self, sample_table):
        gen1 = MockDataGenerator(seed=99)
        rows1 = gen1.generate_rows(sample_table, 10)
        gen2 = MockDataGenerator(seed=99)
        rows2 = gen2.generate_rows(sample_table, 10)
        assert rows1 == rows2


class TestGenerateCSV:
    def test_csv_has_header(self, generator, sample_table):
        csv_str = generator.generate_csv(sample_table, 5)
        reader = csv.DictReader(io.StringIO(csv_str))
        assert set(reader.fieldnames) == {c.name for c in sample_table.columns}

    def test_csv_row_count(self, generator, sample_table):
        csv_str = generator.generate_csv(sample_table, 25)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 25

    def test_csv_parseable(self, generator, sample_table):
        csv_str = generator.generate_csv(sample_table, 10)
        reader = csv.DictReader(io.StringIO(csv_str))
        for row in reader:
            assert "subscriber_id" in row


class TestGenerateJSONL:
    def test_jsonl_line_count(self, generator, sample_table):
        jsonl = generator.generate_jsonl(sample_table, 15)
        lines = [l for l in jsonl.strip().split("\n") if l]
        assert len(lines) == 15

    def test_jsonl_parseable(self, generator, sample_table):
        jsonl = generator.generate_jsonl(sample_table, 10)
        for line in jsonl.strip().split("\n"):
            parsed = json.loads(line)
            assert "subscriber_id" in parsed


class TestGenerateAll:
    def test_returns_dict(self, generator, sample_table):
        result = generator.generate_all((sample_table,), 5)
        assert isinstance(result, dict)
        assert "subscriber_profile.csv" in result

    def test_jsonl_format(self, generator, sample_table):
        result = generator.generate_all((sample_table,), 5, fmt="jsonl")
        assert "subscriber_profile.jsonl" in result

    def test_multiple_tables(self, generator):
        t1 = Table(name="table_a", telco_domain=TelcoDomain.SUBSCRIBER,
                   columns=(Column(name="id", bigquery_type=BigQueryType.STRING),))
        t2 = Table(name="table_b", telco_domain=TelcoDomain.CDR_EVENT,
                   columns=(Column(name="id", bigquery_type=BigQueryType.STRING),))
        result = generator.generate_all((t1, t2), 3)
        assert len(result) == 2
        assert "table_a.csv" in result
        assert "table_b.csv" in result
