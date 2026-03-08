export interface VendorInfo {
  name: string
  supported_domains: string[]
  mapping_count: number
}

export interface DomainInfo {
  name: string
  table_count: number
  tables: string[]
}

export interface ColumnDetail {
  name: string
  bigquery_type: string
  description: string
  nullable: boolean
  pii_category: string | null
}

export interface TableDetail {
  name: string
  telco_domain: string
  column_count: number
  columns: ColumnDetail[]
}

export interface DomainDetail {
  name: string
  table_count: number
  tables: TableDetail[]
}

export interface JurisdictionInfo {
  code: string
  name: string
  framework: string
  gcp_region: string
  data_residency_required: boolean
  rule_count: number
}

export interface ExportRequest {
  domains: string[]
  jurisdiction: string
  vendor?: string
  include_terraform: boolean
  include_pipelines: boolean
  include_dags: boolean
  include_compliance: boolean
}

export interface ExportFileInfo {
  name: string
  size: number
  type: string
}

export interface ExportResponse {
  success: boolean
  file_count: number
  files: ExportFileInfo[]
  download_id: string
}

export interface ComplianceFinding {
  rule_id: string
  framework: string
  data_residency_required: boolean
  encryption_required: boolean
}

export interface ComplianceCheckResponse {
  jurisdiction: string
  framework: string
  finding_count: number
  findings: ComplianceFinding[]
}

export interface AnalyticsTemplateInfo {
  name: string
  type: string
}

export interface HealthResponse {
  status: string
  version: string
}
