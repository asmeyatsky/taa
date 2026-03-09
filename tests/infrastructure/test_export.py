"""Tests for export infrastructure: ZIP building, manifest, file generation, and store cleanup."""

from __future__ import annotations

import json
import os
import tempfile
import time
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from taa.infrastructure.export.manifest import ManifestGenerator
from taa.infrastructure.export.zip_builder import ZipBuilder
from taa.infrastructure.export.file_generator import FileGenerator, ExportStore
from taa.application.dtos.models import GenerationRequest, GenerationResult


# ---------------------------------------------------------------------------
# ManifestGenerator
# ---------------------------------------------------------------------------

class TestManifestGenerator:
    def setup_method(self):
        self.gen = ManifestGenerator()

    def test_manifest_contains_required_fields(self):
        raw = self.gen.generate(
            domains=["subscriber", "cdr_event"],
            tables=["subscriber_profile", "voice_cdr"],
            jurisdiction="SA",
        )
        manifest = json.loads(raw)
        assert manifest["generator"] == "TAA - Telco Analytics Accelerator"
        assert "version" in manifest
        assert "generated_at" in manifest
        assert manifest["domains"] == ["cdr_event", "subscriber"]  # sorted
        assert manifest["tables"] == ["subscriber_profile", "voice_cdr"]  # sorted
        assert manifest["table_count"] == 2
        assert manifest["jurisdiction"] == "SA"

    def test_manifest_includes_vendor_when_provided(self):
        raw = self.gen.generate(
            domains=["subscriber"],
            tables=["subscriber_profile"],
            jurisdiction="SA",
            vendor="amdocs",
        )
        manifest = json.loads(raw)
        assert manifest["vendor"] == "amdocs"

    def test_manifest_vendor_null_when_omitted(self):
        raw = self.gen.generate(
            domains=["subscriber"],
            tables=[],
            jurisdiction="SA",
        )
        manifest = json.loads(raw)
        assert manifest["vendor"] is None

    def test_manifest_artifact_types_respect_flags(self):
        raw = self.gen.generate(
            domains=[],
            tables=[],
            jurisdiction="SA",
            include_terraform=False,
            include_pipelines=False,
            include_dags=True,
            include_compliance=False,
        )
        manifest = json.loads(raw)
        assert "terraform" not in manifest["artifact_types"]
        assert "dataflow_pipelines" not in manifest["artifact_types"]
        assert "compliance_reports" not in manifest["artifact_types"]
        assert "airflow_dags" in manifest["artifact_types"]
        assert "bigquery_ddl" in manifest["artifact_types"]

    def test_manifest_includes_file_entries(self):
        entries = [
            {"path": "bigquery/subscriber.sql", "size": 1234, "type": "sql"},
        ]
        raw = self.gen.generate(
            domains=["subscriber"],
            tables=["subscriber_profile"],
            jurisdiction="SA",
            file_entries=entries,
        )
        manifest = json.loads(raw)
        assert manifest["file_count"] == 1
        assert manifest["files"] == entries

    def test_manifest_is_valid_json(self):
        raw = self.gen.generate(
            domains=["subscriber"],
            tables=[],
            jurisdiction="SA",
        )
        # Should not raise
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)


# ---------------------------------------------------------------------------
# ZipBuilder
# ---------------------------------------------------------------------------

class TestZipBuilder:
    def setup_method(self):
        self.builder = ZipBuilder()

    def test_build_from_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_bytes, file_infos = self.builder.build_from_directory(
                Path(tmpdir),
                domains=["subscriber"],
                jurisdiction="SA",
            )
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            names = zf.namelist()
            # Even an empty source dir should contain manifest + README
            assert "manifest.json" in names
            assert "README.md" in names
            zf.close()

    def test_build_preserves_directory_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mini artefact tree
            bq_dir = Path(tmpdir) / "bigquery"
            bq_dir.mkdir()
            (bq_dir / "subscriber.sql").write_text("CREATE TABLE subscriber;")

            tf_dir = Path(tmpdir) / "terraform"
            tf_dir.mkdir()
            (tf_dir / "main.tf").write_text("provider \"google\" {}")

            zip_bytes, file_infos = self.builder.build_from_directory(
                Path(tmpdir),
                domains=["subscriber"],
                jurisdiction="SA",
            )

            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            names = zf.namelist()
            assert "bigquery/subscriber.sql" in names
            assert "terraform/main.tf" in names
            assert "manifest.json" in names
            assert "README.md" in names
            zf.close()

    def test_build_file_infos_match_zip_contents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bq_dir = Path(tmpdir) / "bigquery"
            bq_dir.mkdir()
            (bq_dir / "subscriber.sql").write_text("SELECT 1;")

            zip_bytes, file_infos = self.builder.build_from_directory(
                Path(tmpdir),
                domains=["subscriber"],
            )

            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            zip_names = set(zf.namelist())
            info_paths = {fi["path"] for fi in file_infos}
            assert info_paths == zip_names
            zf.close()

    def test_build_manifest_embedded_in_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bq_dir = Path(tmpdir) / "bigquery"
            bq_dir.mkdir()
            (bq_dir / "subscriber.sql").write_text("CREATE TABLE t;")

            zip_bytes, _ = self.builder.build_from_directory(
                Path(tmpdir),
                domains=["subscriber"],
                jurisdiction="SA",
                vendor="amdocs",
            )

            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            manifest_raw = zf.read("manifest.json").decode("utf-8")
            manifest = json.loads(manifest_raw)
            assert manifest["jurisdiction"] == "SA"
            assert manifest["vendor"] == "amdocs"
            assert "subscriber" in manifest["domains"]
            zf.close()

    def test_build_readme_embedded_in_zip(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_bytes, _ = self.builder.build_from_directory(
                Path(tmpdir),
                domains=["subscriber"],
            )
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            readme = zf.read("README.md").decode("utf-8")
            assert "TAA Export Pack" in readme
            assert "subscriber" in readme
            zf.close()

    def test_build_respects_artefact_flags_in_readme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_bytes, _ = self.builder.build_from_directory(
                Path(tmpdir),
                domains=["subscriber"],
                include_terraform=False,
                include_dags=False,
            )
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            readme = zf.read("README.md").decode("utf-8")
            # Terraform and DAG rows should be absent from the table
            assert "terraform/" not in readme.lower().split("## usage")[0]
            assert "airflow/" not in readme.lower().split("## usage")[0]
            zf.close()

    def test_build_collects_table_names_from_bigquery_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bq_dir = Path(tmpdir) / "bigquery"
            bq_dir.mkdir()
            (bq_dir / "subscriber.sql").write_text("DDL subscriber")
            (bq_dir / "cdr_event.sql").write_text("DDL cdr_event")

            zip_bytes, _ = self.builder.build_from_directory(
                Path(tmpdir),
                domains=["subscriber", "cdr_event"],
            )
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            manifest = json.loads(zf.read("manifest.json"))
            assert "subscriber" in manifest["tables"]
            assert "cdr_event" in manifest["tables"]
            zf.close()

    def test_zip_is_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bq_dir = Path(tmpdir) / "bigquery"
            bq_dir.mkdir()
            (bq_dir / "test.sql").write_text("CREATE TABLE x;")

            zip_bytes, _ = self.builder.build_from_directory(Path(tmpdir))
            # Should not raise
            zf = zipfile.ZipFile(BytesIO(zip_bytes))
            assert zf.testzip() is None  # No bad CRC
            zf.close()


# ---------------------------------------------------------------------------
# ExportStore (TTL cleanup)
# ---------------------------------------------------------------------------

class TestExportStore:
    def test_put_and_get(self):
        store = ExportStore(ttl_seconds=60)
        data = b"fake zip data"
        eid = store.put(data)
        assert store.get(eid) == data

    def test_get_missing_returns_none(self):
        store = ExportStore()
        assert store.get("nonexistent-id") is None

    def test_expired_entries_return_none(self):
        store = ExportStore(ttl_seconds=0)  # immediate expiry
        eid = store.put(b"data")
        # Entry should be expired by now (ttl=0)
        assert store.get(eid) is None

    def test_cleanup_removes_expired(self):
        # Use a very short TTL so entries expire between put and cleanup.
        store = ExportStore(ttl_seconds=0)
        store.put(b"a")
        store.put(b"b")
        # Some entries may have been evicted already during the second put,
        # but cleanup should bring the store to 0 regardless.
        removed = store.cleanup()
        assert removed >= 0
        assert store.size == 0

    def test_max_size_evicts_oldest(self):
        store = ExportStore(ttl_seconds=600, max_size=2)
        id1 = store.put(b"first")
        _id2 = store.put(b"second")
        _id3 = store.put(b"third")  # should evict id1
        assert store.get(id1) is None
        assert store.size == 2

    def test_size_property(self):
        store = ExportStore(ttl_seconds=600)
        assert store.size == 0
        store.put(b"data")
        assert store.size == 1


# ---------------------------------------------------------------------------
# FileGenerator (integration with GenerateFullPackCommand)
# ---------------------------------------------------------------------------

class TestFileGenerator:
    def test_generate_and_package_creates_valid_zip(self):
        """Use a fake generate function that writes files to output_dir."""
        gen = FileGenerator()

        def fake_generate(request: GenerationRequest) -> GenerationResult:
            bq_dir = request.output_dir / "bigquery"
            bq_dir.mkdir(parents=True, exist_ok=True)
            (bq_dir / "subscriber.sql").write_text("CREATE TABLE subscriber_profile;")
            return GenerationResult(
                success=True,
                files_generated=[str(bq_dir / "subscriber.sql")],
            )

        request = GenerationRequest(
            domains=["subscriber"],
            jurisdiction="SA",
        )

        result, zip_bytes, file_infos = gen.generate_and_package(
            generate_fn=fake_generate,
            request=request,
        )

        assert result.success is True
        assert len(zip_bytes) > 0

        zf = zipfile.ZipFile(BytesIO(zip_bytes))
        names = zf.namelist()
        assert "bigquery/subscriber.sql" in names
        assert "manifest.json" in names
        assert "README.md" in names

        # Verify manifest content
        manifest = json.loads(zf.read("manifest.json"))
        assert "subscriber" in manifest["domains"]
        assert manifest["jurisdiction"] == "SA"
        zf.close()

    def test_generate_and_package_with_multiple_artefact_types(self):
        gen = FileGenerator()

        def fake_generate(request: GenerationRequest) -> GenerationResult:
            files: list[str] = []
            for subdir, fname, content in [
                ("bigquery", "subscriber.sql", "CREATE TABLE t;"),
                ("airflow", "daily_cdr_processing.py", "# DAG"),
                ("terraform", "main.tf", 'provider "google" {}'),
                ("dataflow", "cdr_mediation.py", "# Pipeline"),
                ("compliance", "subscriber_compliance.json", '{"rules": []}'),
            ]:
                d = request.output_dir / subdir
                d.mkdir(parents=True, exist_ok=True)
                (d / fname).write_text(content)
                files.append(str(d / fname))
            return GenerationResult(success=True, files_generated=files)

        request = GenerationRequest(
            domains=["subscriber"],
            jurisdiction="SA",
        )

        result, zip_bytes, file_infos = gen.generate_and_package(
            generate_fn=fake_generate,
            request=request,
        )

        zf = zipfile.ZipFile(BytesIO(zip_bytes))
        names = zf.namelist()
        assert "bigquery/subscriber.sql" in names
        assert "airflow/daily_cdr_processing.py" in names
        assert "terraform/main.tf" in names
        assert "dataflow/cdr_mediation.py" in names
        assert "compliance/subscriber_compliance.json" in names
        assert "manifest.json" in names
        assert "README.md" in names
        zf.close()

    def test_generate_and_package_passes_flags_to_manifest(self):
        gen = FileGenerator()

        def fake_generate(request: GenerationRequest) -> GenerationResult:
            bq_dir = request.output_dir / "bigquery"
            bq_dir.mkdir(parents=True, exist_ok=True)
            (bq_dir / "test.sql").write_text("SELECT 1;")
            return GenerationResult(success=True, files_generated=["test.sql"])

        request = GenerationRequest(
            domains=["subscriber"],
            jurisdiction="AE",
            include_terraform=False,
            include_pipelines=False,
            include_dags=False,
            include_compliance=False,
        )

        _, zip_bytes, _ = gen.generate_and_package(
            generate_fn=fake_generate,
            request=request,
        )

        zf = zipfile.ZipFile(BytesIO(zip_bytes))
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["jurisdiction"] == "AE"
        assert manifest["flags"]["include_terraform"] is False
        assert manifest["flags"]["include_pipelines"] is False
        assert manifest["flags"]["include_dags"] is False
        assert manifest["flags"]["include_compliance"] is False
        assert "bigquery_ddl" in manifest["artifact_types"]
        assert "terraform" not in manifest["artifact_types"]
        zf.close()

    def test_generate_propagates_errors_in_result(self):
        gen = FileGenerator()

        def failing_generate(request: GenerationRequest) -> GenerationResult:
            # Still write at least an empty dir so zip works
            (request.output_dir / "bigquery").mkdir(parents=True, exist_ok=True)
            return GenerationResult(
                success=False,
                errors=["Something went wrong"],
            )

        request = GenerationRequest(domains=["subscriber"])
        result, zip_bytes, _ = gen.generate_and_package(
            generate_fn=failing_generate,
            request=request,
        )
        assert result.success is False
        assert "Something went wrong" in result.errors
        # ZIP should still be generated (even if empty of artefacts)
        assert len(zip_bytes) > 0
