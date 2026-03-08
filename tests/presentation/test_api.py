"""Tests for TAA FastAPI endpoints."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from taa.presentation.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealth:
    def test_health_check(self, client: TestClient):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestBSS:
    def test_list_vendors(self, client: TestClient):
        r = client.get("/api/bss/vendors")
        assert r.status_code == 200
        vendors = r.json()
        assert isinstance(vendors, list)
        assert len(vendors) >= 1
        assert "name" in vendors[0]
        assert "supported_domains" in vendors[0]
        assert "mapping_count" in vendors[0]

    def test_upload_schema(self, client: TestClient):
        csv_content = (
            "table,column,type,nullable\n"
            "subscriber_profile,subscriber_id,STRING,NO\n"
            "subscriber_profile,msisdn,STRING,NO\n"
            "subscriber_profile,first_name,STRING,YES\n"
        )
        r = client.post("/api/bss/schema", json={"content": csv_content, "format": "csv"})
        assert r.status_code == 200
        data = r.json()
        assert "tables_found" in data
        assert "columns_found" in data


class TestDomain:
    def test_list_domains(self, client: TestClient):
        r = client.get("/api/domain/list")
        assert r.status_code == 200
        domains = r.json()
        assert isinstance(domains, list)
        assert len(domains) >= 7
        assert "name" in domains[0]
        assert "table_count" in domains[0]

    def test_ldm(self, client: TestClient):
        r = client.post("/api/domain/ldm", json={"domains": ["subscriber"]})
        assert r.status_code == 200
        data = r.json()
        assert "domains" in data
        assert len(data["domains"]) == 1
        domain = data["domains"][0]
        assert domain["name"] == "subscriber"
        assert domain["table_count"] >= 1
        assert len(domain["tables"]) >= 1
        table = domain["tables"][0]
        assert "columns" in table
        assert len(table["columns"]) >= 1
        col = table["columns"][0]
        assert "name" in col
        assert "bigquery_type" in col

    def test_ldm_multiple_domains(self, client: TestClient):
        r = client.post("/api/domain/ldm", json={"domains": ["subscriber", "product_catalogue"]})
        assert r.status_code == 200
        data = r.json()
        assert len(data["domains"]) == 2


class TestBigQueryExport:
    def test_export_pack(self, client: TestClient):
        r = client.post("/api/bigquery/export", json={
            "domains": ["subscriber"],
            "jurisdiction": "SA",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["file_count"] >= 1
        assert len(data["files"]) >= 1
        assert "download_id" in data

    def test_download_zip(self, client: TestClient):
        # Generate first
        r1 = client.post("/api/bigquery/export", json={"domains": ["subscriber"]})
        download_id = r1.json()["download_id"]

        # Download
        r2 = client.get(f"/api/bigquery/download/{download_id}")
        assert r2.status_code == 200
        assert r2.headers["content-type"] == "application/zip"

        # Validate it's a valid ZIP
        zf = zipfile.ZipFile(BytesIO(r2.content))
        assert len(zf.namelist()) >= 1
        zf.close()

    def test_download_not_found(self, client: TestClient):
        r = client.get("/api/bigquery/download/nonexistent-id")
        assert r.status_code == 404

    def test_export_with_artefact_flags(self, client: TestClient):
        r = client.post("/api/bigquery/export", json={
            "domains": ["subscriber"],
            "include_terraform": False,
            "include_pipelines": False,
            "include_dags": False,
            "include_compliance": False,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        # Should only have DDL files
        for f in data["files"]:
            assert "terraform" not in f["name"].lower()
            assert "dataflow" not in f["name"].lower()


class TestCompliance:
    def test_list_jurisdictions(self, client: TestClient):
        r = client.get("/api/compliance/jurisdictions")
        assert r.status_code == 200
        jurs = r.json()
        assert isinstance(jurs, list)
        assert len(jurs) >= 5
        j = jurs[0]
        assert "code" in j
        assert "name" in j
        assert "framework" in j

    def test_check_compliance(self, client: TestClient):
        r = client.post("/api/compliance/check", json={
            "domains": ["subscriber"],
            "jurisdiction": "SA",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["jurisdiction"] == "SA"
        assert data["framework"] == "PDPL"
        assert data["finding_count"] >= 1
        assert len(data["findings"]) >= 1
        finding = data["findings"][0]
        assert "rule_id" in finding
        assert "framework" in finding

    def test_compliance_report(self, client: TestClient):
        r = client.get("/api/compliance/report", params={
            "domains": "subscriber",
            "jurisdiction": "SA",
        })
        assert r.status_code == 200
        assert "text" in r.headers["content-type"]


class TestAnalytics:
    def test_list_templates(self, client: TestClient):
        r = client.get("/api/analytics/templates")
        assert r.status_code == 200
        templates = r.json()
        assert isinstance(templates, list)
        assert len(templates) >= 5
        types_found = {t["type"] for t in templates}
        assert "sql" in types_found
        assert "notebook" in types_found
        assert "dashboard" in types_found

    def test_generate_sql_template(self, client: TestClient):
        # Get list first
        templates = client.get("/api/analytics/templates").json()
        sql_template = next(t for t in templates if t["type"] == "sql")

        r = client.post("/api/analytics/generate", params={
            "name": sql_template["name"],
            "template_type": "sql",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "sql"
        assert len(data["content"]) > 0

    def test_generate_notebook_template(self, client: TestClient):
        templates = client.get("/api/analytics/templates").json()
        nb_template = next(t for t in templates if t["type"] == "notebook")

        r = client.post("/api/analytics/generate", params={
            "name": nb_template["name"],
            "template_type": "notebook",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "notebook"
        # Notebook content should be valid JSON (ipynb format)
        nb = json.loads(data["content"])
        assert "cells" in nb

    def test_generate_dashboard_template(self, client: TestClient):
        templates = client.get("/api/analytics/templates").json()
        dash_template = next(t for t in templates if t["type"] == "dashboard")

        r = client.post("/api/analytics/generate", params={
            "name": dash_template["name"],
            "template_type": "dashboard",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["type"] == "dashboard"


class TestMockData:
    def test_generate_mock_data(self, client: TestClient):
        r = client.post("/api/mock/generate", json={
            "domains": ["subscriber"],
            "rows": 5,
            "format": "csv",
        })
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"

        zf = zipfile.ZipFile(BytesIO(r.content))
        names = zf.namelist()
        assert len(names) >= 1
        assert any("subscriber" in n for n in names)
        zf.close()

    def test_generate_mock_data_jsonl(self, client: TestClient):
        r = client.post("/api/mock/generate", json={
            "domains": ["subscriber"],
            "rows": 3,
            "format": "jsonl",
        })
        assert r.status_code == 200
        zf = zipfile.ZipFile(BytesIO(r.content))
        names = zf.namelist()
        assert any(n.endswith(".jsonl") for n in names)
        zf.close()
