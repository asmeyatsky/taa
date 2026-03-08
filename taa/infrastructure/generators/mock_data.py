"""Mock data generator for synthetic BSS test data."""

from __future__ import annotations

import csv
import io
import json
import random
import string
from datetime import datetime, timedelta
from typing import Any

from taa.domain.entities.table import Table
from taa.domain.entities.column import Column
from taa.domain.value_objects.enums import BigQueryType, PIICategory


# --- Synthetic value generators per data type and PII category ---

_FIRST_NAMES = ["Ahmed", "Sara", "Mohammed", "Fatima", "John", "Mary", "Wei", "Priya", "Omar", "Layla"]
_LAST_NAMES = ["Al-Rashid", "Khan", "Smith", "Patel", "Zhang", "Kumar", "Hassan", "Ali", "Müller", "O'Brien"]
_CITIES = ["Riyadh", "Dubai", "London", "Mumbai", "Cairo", "Istanbul", "Kuwait City", "Doha", "Jeddah", "Abu Dhabi"]
_COUNTRIES = ["SA", "AE", "GB", "IN", "EG", "TR", "KW", "QA", "BH", "ZA"]
_STATUSES = ["active", "inactive", "suspended", "pending", "terminated"]
_PLAN_NAMES = ["Gold 5G", "Silver 4G", "Platinum Unlimited", "Business Pro", "Prepaid Basic"]
_TECHNOLOGIES = ["4G", "5G NR", "3G", "FBB", "VoLTE"]
_PAYMENT_METHODS = ["credit_card", "direct_debit", "prepaid", "bank_transfer", "mobile_wallet"]


def _random_msisdn() -> str:
    cc = random.choice(["966", "971", "44", "91", "20", "90"])
    return f"+{cc}{random.randint(500000000, 599999999)}"


def _random_imsi() -> str:
    return f"{random.randint(200, 999)}{random.randint(10, 99)}{random.randint(1000000000, 9999999999)}"


def _random_imei() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(15))


def _random_email(idx: int) -> str:
    name = random.choice(_FIRST_NAMES).lower()
    return f"{name}.{idx}@example.com"


def _random_national_id() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(10))


def _random_ip() -> str:
    return f"{random.randint(10, 192)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def _random_date(start_year: int = 2020, end_year: int = 2026) -> str:
    start = datetime(start_year, 1, 1)
    days = (datetime(end_year, 1, 1) - start).days
    dt = start + timedelta(days=random.randint(0, max(days, 1)))
    return dt.strftime("%Y-%m-%d")


def _random_timestamp(start_year: int = 2024, end_year: int = 2026) -> str:
    start = datetime(start_year, 1, 1)
    secs = int((datetime(end_year, 1, 1) - start).total_seconds())
    dt = start + timedelta(seconds=random.randint(0, max(secs, 1)))
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _generate_value(column: Column, row_idx: int) -> Any:
    """Generate a synthetic value for a column based on its type and PII category."""
    # Nullable columns: ~5% chance of null
    if column.nullable and random.random() < 0.05:
        return None

    # PII-specific generators
    if column.pii_category == PIICategory.MSISDN:
        return _random_msisdn()
    if column.pii_category == PIICategory.IMSI:
        return _random_imsi()
    if column.pii_category == PIICategory.IMEI:
        return _random_imei()
    if column.pii_category == PIICategory.EMAIL:
        return _random_email(row_idx)
    if column.pii_category == PIICategory.NATIONAL_ID:
        return _random_national_id()
    if column.pii_category == PIICategory.NAME:
        return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_NAMES)}"
    if column.pii_category == PIICategory.ADDRESS:
        return f"{random.randint(1, 999)} {random.choice(['King Fahd Rd', 'Sheikh Zayed Rd', 'High St', 'MG Road', 'Tahrir St'])}, {random.choice(_CITIES)}"
    if column.pii_category == PIICategory.DATE_OF_BIRTH:
        return _random_date(1960, 2005)
    if column.pii_category == PIICategory.IP_ADDRESS:
        return _random_ip()
    if column.pii_category == PIICategory.LOCATION:
        lat = random.uniform(20.0, 55.0)
        lng = random.uniform(30.0, 80.0)
        return f"{lat:.6f},{lng:.6f}"

    # Type-based generators with column name heuristics
    name_lower = column.name.lower()

    if column.bigquery_type == BigQueryType.STRING:
        if "status" in name_lower:
            return random.choice(_STATUSES)
        if "country" in name_lower or "jurisdiction" in name_lower:
            return random.choice(_COUNTRIES)
        if "city" in name_lower:
            return random.choice(_CITIES)
        if "technology" in name_lower or "tech" in name_lower:
            return random.choice(_TECHNOLOGIES)
        if "plan" in name_lower or "product" in name_lower:
            return random.choice(_PLAN_NAMES)
        if "payment" in name_lower:
            return random.choice(_PAYMENT_METHODS)
        if "segment" in name_lower:
            return random.choice(["consumer", "enterprise", "sme", "government", "vip"])
        if "type" in name_lower:
            return random.choice(["voice", "data", "sms", "vas", "roaming"])
        if name_lower.endswith("_id") or name_lower == "id":
            return f"{column.name.upper()}-{row_idx:06d}"
        return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

    if column.bigquery_type in (BigQueryType.INT64,):
        if "duration" in name_lower or "seconds" in name_lower:
            return random.randint(0, 3600)
        if "count" in name_lower:
            return random.randint(0, 1000)
        if "age" in name_lower:
            return random.randint(18, 80)
        return random.randint(0, 100000)

    if column.bigquery_type in (BigQueryType.FLOAT64, BigQueryType.NUMERIC, BigQueryType.BIGNUMERIC):
        if "amount" in name_lower or "charge" in name_lower or "fee" in name_lower or "revenue" in name_lower:
            return round(random.uniform(0, 5000), 2)
        if "rate" in name_lower or "pct" in name_lower or "percentage" in name_lower:
            return round(random.uniform(0, 100), 2)
        if "score" in name_lower:
            return round(random.uniform(0, 1), 4)
        if "lat" in name_lower:
            return round(random.uniform(20.0, 55.0), 6)
        if "lon" in name_lower or "lng" in name_lower:
            return round(random.uniform(30.0, 80.0), 6)
        return round(random.uniform(0, 10000), 2)

    if column.bigquery_type == BigQueryType.BOOLEAN:
        return random.choice([True, False])

    if column.bigquery_type == BigQueryType.DATE:
        return _random_date()

    if column.bigquery_type in (BigQueryType.TIMESTAMP, BigQueryType.DATETIME):
        return _random_timestamp()

    return f"val_{row_idx}"


class MockDataGenerator:
    """Generates synthetic test data for TAA domain tables."""

    def __init__(self, seed: int | None = None) -> None:
        if seed is not None:
            random.seed(seed)

    def generate_rows(self, table: Table, row_count: int = 100) -> list[dict[str, Any]]:
        """Generate a list of dicts representing rows for a table."""
        rows = []
        for i in range(row_count):
            row = {}
            for col in table.columns:
                row[col.name] = _generate_value(col, i)
            rows.append(row)
        return rows

    def generate_csv(self, table: Table, row_count: int = 100) -> str:
        """Generate CSV string for a table."""
        rows = self.generate_rows(table, row_count)
        if not rows:
            return ""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def generate_jsonl(self, table: Table, row_count: int = 100) -> str:
        """Generate JSONL (newline-delimited JSON) for a table."""
        rows = self.generate_rows(table, row_count)
        return "\n".join(json.dumps(row, default=str) for row in rows) + "\n"

    def generate_all(
        self, tables: tuple[Table, ...], row_count: int = 100, fmt: str = "csv",
    ) -> dict[str, str]:
        """Generate mock data for multiple tables. Returns {filename: content}."""
        results = {}
        ext = "csv" if fmt == "csv" else "jsonl"
        for table in tables:
            if fmt == "csv":
                content = self.generate_csv(table, row_count)
            else:
                content = self.generate_jsonl(table, row_count)
            results[f"{table.name}.{ext}"] = content
        return results
