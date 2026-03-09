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
  AuditListResponse,
  AuditStats,
} from './types'

const BASE = '/api'

function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('taa_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`)
  return res.json()
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`)
  return res.json()
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  })
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`)
}

export interface ApiUser {
  id: string
  username: string
  name: string
  email: string
  role: string
  disabled: boolean
  created_at: string | null
  updated_at: string | null
}

export interface CreateUserRequest {
  username: string
  name?: string
  email?: string
  role?: string
  password: string
}

export interface UpdateUserRequest {
  name?: string
  email?: string
  role?: string
  password?: string
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
      headers: getAuthHeaders(),
    }).then(r => {
      if (!r.ok) throw new Error(`Generate template failed: ${r.status}`)
      return r.json() as Promise<{ name: string; type: string; content: string }>
    }),

  // Mock Data
  generateMockData: (domains: string[], rows: number, format: string) =>
    fetch(`${BASE}/mock/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify({ domains, rows, format }),
    }),

  // User Management
  getUsers: () => get<ApiUser[]>('/users/'),
  getUser: (id: string) => get<ApiUser>(`/users/${id}`),
  createUser: (data: CreateUserRequest) => post<ApiUser>('/users/', data),
  updateUser: (id: string, data: UpdateUserRequest) => put<ApiUser>(`/users/${id}`, data),
  deleteUser: (id: string) => del(`/users/${id}`),
  resetPassword: (id: string, newPassword: string) =>
    post<ApiUser>(`/users/${id}/reset-password`, { new_password: newPassword }),

  // Audit
  getAuditEntries: (params: {
    page?: number
    page_size?: number
    user_id?: string
    action?: string
    since?: string
  } = {}) => {
    const qs = new URLSearchParams()
    if (params.page) qs.set('page', String(params.page))
    if (params.page_size) qs.set('page_size', String(params.page_size))
    if (params.user_id) qs.set('user_id', params.user_id)
    if (params.action) qs.set('action', params.action)
    if (params.since) qs.set('since', params.since)
    return get<AuditListResponse>(`/audit/?${qs.toString()}`)
  },

  getAuditByUser: (userId: string, page = 1) =>
    get<AuditListResponse>(`/audit/user/${encodeURIComponent(userId)}?page=${page}`),

  getAuditByAction: (action: string, page = 1) =>
    get<AuditListResponse>(`/audit/action/${encodeURIComponent(action)}?page=${page}`),

  getAuditStats: () => get<AuditStats>('/audit/stats'),
}
