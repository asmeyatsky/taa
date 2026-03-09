"""Manifest generator for export ZIP archives."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import taa


class ManifestGenerator:
    """Generates manifest.json metadata for inclusion in export ZIPs."""

    def generate(
        self,
        *,
        domains: list[str],
        tables: list[str],
        jurisdiction: str,
        vendor: str | None = None,
        file_entries: list[dict[str, Any]] | None = None,
        include_terraform: bool = True,
        include_pipelines: bool = True,
        include_dags: bool = True,
        include_compliance: bool = True,
    ) -> str:
        """Generate a manifest.json string with export metadata.

        Args:
            domains: List of domain names included in the export.
            tables: List of table names across all domains.
            jurisdiction: Jurisdiction code used for generation.
            vendor: Optional BSS vendor name.
            file_entries: Optional list of file metadata dicts with
                          keys ``path``, ``size``, and ``type``.
            include_terraform: Whether Terraform files were included.
            include_pipelines: Whether pipeline files were included.
            include_dags: Whether DAG files were included.
            include_compliance: Whether compliance reports were included.

        Returns:
            JSON string of the manifest.
        """
        now = datetime.now(timezone.utc)

        artifact_types: list[str] = ["bigquery_ddl"]
        if include_terraform:
            artifact_types.append("terraform")
        if include_pipelines:
            artifact_types.append("dataflow_pipelines")
        if include_dags:
            artifact_types.append("airflow_dags")
        if include_compliance:
            artifact_types.append("compliance_reports")

        manifest: dict[str, Any] = {
            "generator": "TAA - Telco Analytics Accelerator",
            "version": taa.__version__,
            "generated_at": now.isoformat(),
            "domains": sorted(domains),
            "tables": sorted(tables),
            "table_count": len(tables),
            "jurisdiction": jurisdiction,
            "vendor": vendor,
            "artifact_types": artifact_types,
            "flags": {
                "include_terraform": include_terraform,
                "include_pipelines": include_pipelines,
                "include_dags": include_dags,
                "include_compliance": include_compliance,
            },
        }

        if file_entries is not None:
            manifest["files"] = file_entries
            manifest["file_count"] = len(file_entries)

        return json.dumps(manifest, indent=2)
