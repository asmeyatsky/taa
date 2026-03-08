import type {
  VendorInfo,
  DomainInfo,
  DomainDetail,
  JurisdictionInfo,
  ExportRequest,
  ExportResponse,
  ComplianceCheckResponse,
  AnalyticsTemplateInfo,
  HealthResponse,
} from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

export const api = {
  health: () => get<HealthResponse>('/health'),

  // BSS
  getVendors: () => get<VendorInfo[]>('/bss/vendors'),

  // Domain
  getDomains: () => get<DomainInfo[]>('/domain/list'),
  getLDM: (domains: string[], vendor?: string) =>
    post<{ domains: DomainDetail[] }>('/domain/ldm', { domains, vendor }),

  // BigQuery Export
  exportPack: (req: ExportRequest) => post<ExportResponse>('/bigquery/export', req),
  getDownloadUrl: (id: string) => `${BASE}/bigquery/download/${id}`,

  // Compliance
  getJurisdictions: () => get<JurisdictionInfo[]>('/compliance/jurisdictions'),
  checkCompliance: (domains: string[], jurisdiction: string) =>
    post<ComplianceCheckResponse>('/compliance/check', { domains, jurisdiction }),

  // Analytics
  getTemplates: () => get<AnalyticsTemplateInfo[]>('/analytics/templates'),
  generateTemplate: (name: string, templateType: string) =>
    fetch(`${BASE}/analytics/generate?name=${encodeURIComponent(name)}&template_type=${encodeURIComponent(templateType)}`, {
      method: 'POST',
    }).then(r => {
      if (!r.ok) throw new Error(`Generate template failed: ${r.status}`)
      return r.json() as Promise<{ name: string; type: string; content: string }>
    }),

  // Mock Data
  generateMockData: (domains: string[], rows: number, format: string) =>
    fetch(`${BASE}/mock/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domains, rows, format }),
    }),
}
