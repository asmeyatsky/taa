"""API-specific request/response models."""

from __future__ import annotations

from pydantic import BaseModel


# --- BSS ---

class SchemaUploadRequest(BaseModel):
    content: str
    format: str = "auto"


class MappingSuggestionItem(BaseModel):
    vendor_table: str
    vendor_field: str
    canonical_table: str
    canonical_field: str
    confidence: float
    match_reason: str = ""


class SchemaUploadResponse(BaseModel):
    tables_found: int
    columns_found: int
    detected_vendor: str | None
    vendor_confidence: float
    suggestions: list[MappingSuggestionItem]
    mapping_coverage_pct: float
    import_coverage_pct: float


# --- Domain ---

class ColumnDetail(BaseModel):
    name: str
    bigquery_type: str
    description: str = ""
    nullable: bool = True
    pii_category: str | None = None


class TableDetail(BaseModel):
    name: str
    telco_domain: str
    column_count: int
    columns: list[ColumnDetail]


class DomainDetail(BaseModel):
    name: str
    table_count: int
    tables: list[TableDetail]


class LDMRequest(BaseModel):
    domains: list[str]
    vendor: str | None = None


class LDMResponse(BaseModel):
    domains: list[DomainDetail]


# --- Export ---

class ExportRequest(BaseModel):
    domains: list[str]
    jurisdiction: str = "SA"
    vendor: str | None = None
    include_terraform: bool = True
    include_pipelines: bool = True
    include_dags: bool = True
    include_compliance: bool = True


class ExportFileInfo(BaseModel):
    name: str
    size: int
    type: str


class ExportResponse(BaseModel):
    success: bool
    file_count: int
    files: list[ExportFileInfo]
    download_id: str


# --- Compliance ---

class ComplianceCheckRequest(BaseModel):
    domains: list[str]
    jurisdiction: str = "SA"


class ComplianceFinding(BaseModel):
    rule_id: str
    framework: str
    data_residency_required: bool
    encryption_required: bool


class ComplianceCheckResponse(BaseModel):
    jurisdiction: str
    framework: str
    finding_count: int
    findings: list[ComplianceFinding]


# --- Mock data ---

class MockDataRequest(BaseModel):
    domains: list[str]
    rows: int = 100
    format: str = "csv"
    seed: int | None = None


# --- Analytics ---

class AnalyticsTemplateInfo(BaseModel):
    name: str
    type: str = "sql"


# --- AI Mapping ---

class AIMappingSuggestionItem(BaseModel):
    vendor_table: str
    vendor_field: str
    canonical_table: str
    canonical_field: str
    confidence: float
    reasoning: str
    transformation: str = ""


class AIMappingResponse(BaseModel):
    suggestions: list[AIMappingSuggestionItem]
    model_used: str
    message: str
    available: bool
