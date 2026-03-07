"""Application DTOs (Pydantic models)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    """Request DTO for code generation commands."""

    domains: list[str] = Field(default_factory=list)
    jurisdiction: str = "SA"
    vendor: str | None = None
    output_dir: Path = Path("./output")
    project_id: str = "telco-analytics"
    gcp_region: str | None = None
    include_terraform: bool = True
    include_pipelines: bool = True
    include_dags: bool = True
    include_compliance: bool = True


class GenerationResult(BaseModel):
    """Result DTO for code generation commands."""

    success: bool = True
    files_generated: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""

    @property
    def file_count(self) -> int:
        return len(self.files_generated)


class DomainInfo(BaseModel):
    """DTO for domain information queries."""

    name: str
    table_count: int = 0
    tables: list[str] = Field(default_factory=list)


class VendorInfo(BaseModel):
    """DTO for vendor information queries."""

    name: str
    supported_domains: list[str] = Field(default_factory=list)
    mapping_count: int = 0


class JurisdictionInfo(BaseModel):
    """DTO for jurisdiction information queries."""

    code: str
    name: str
    framework: str
    gcp_region: str
    data_residency_required: bool
    rule_count: int = 0


class MappingResult(BaseModel):
    """Result DTO for vendor mapping commands."""

    vendor: str
    domain: str
    total_fields: int = 0
    mapped_fields: int = 0
    coverage_pct: float = 0.0
    unmapped_fields: list[str] = Field(default_factory=list)
    conflicts: int = 0
