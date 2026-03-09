import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import type { AuditEntry, AuditStats, AuditListResponse } from '../api/types'

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [stats, setStats] = useState<AuditStats | null>(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(false)

  // Filters
  const [filterUser, setFilterUser] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [filterSince, setFilterSince] = useState('')

  const fetchEntries = useCallback(async () => {
    try {
      const data: AuditListResponse = await api.getAuditEntries({
        page,
        page_size: 50,
        user_id: filterUser || undefined,
        action: filterAction || undefined,
        since: filterSince || undefined,
      })
      setEntries(data.entries)
      setTotalPages(data.pages)
      setTotal(data.total)
    } catch (err) {
      console.error('Failed to fetch audit entries:', err)
    }
    setLoading(false)
  }, [page, filterUser, filterAction, filterSince])

  const fetchStats = useCallback(async () => {
    try {
      const data = await api.getAuditStats()
      setStats(data)
    } catch (err) {
      console.error('Failed to fetch audit stats:', err)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchEntries()
    fetchStats()
  }, [fetchEntries, fetchStats])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      fetchEntries()
      fetchStats()
    }, 10000)
    return () => clearInterval(interval)
  }, [autoRefresh, fetchEntries, fetchStats])

  const handleFilter = () => {
    setPage(1)
    setLoading(true)
    fetchEntries()
    fetchStats()
  }

  const handleClearFilters = () => {
    setFilterUser('')
    setFilterAction('')
    setFilterSince('')
    setPage(1)
  }

  const handleExport = () => {
    const params = new URLSearchParams()
    if (filterUser) params.set('user_id', filterUser)
    if (filterAction) params.set('action', filterAction)
    if (filterSince) params.set('since', filterSince)

    const token = localStorage.getItem('taa_token')
    const url = `/api/audit/export?${params.toString()}`

    fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(r => r.blob())
      .then(blob => {
        const a = document.createElement('a')
        a.href = URL.createObjectURL(blob)
        a.download = 'audit_log.csv'
        a.click()
        URL.revokeObjectURL(a.href)
      })
      .catch(err => console.error('Export failed:', err))
  }

  return (
    <div className="page">
      <h2>Audit Log</h2>
      <p className="page-desc">
        Compliance audit trail tracking all write operations across the platform.
      </p>

      {/* Stats Dashboard */}
      {stats && (
        <div className="audit-stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.total_entries}</div>
            <div className="stat-label">Total Actions</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.unique_users}</div>
            <div className="stat-label">Unique Users</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.today_entries}</div>
            <div className="stat-label">Actions Today</div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="card">
        <h3>Filters</h3>
        <div className="audit-filters">
          <div className="form-field">
            <label>User ID</label>
            <input
              className="input"
              type="text"
              placeholder="Filter by user..."
              value={filterUser}
              onChange={e => setFilterUser(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label>Action</label>
            <select
              className="select"
              value={filterAction}
              onChange={e => setFilterAction(e.target.value)}
            >
              <option value="">All actions</option>
              <option value="create">Create</option>
              <option value="update">Update</option>
              <option value="delete">Delete</option>
            </select>
          </div>
          <div className="form-field">
            <label>Since</label>
            <input
              className="input"
              type="date"
              value={filterSince}
              onChange={e => setFilterSince(e.target.value)}
            />
          </div>
          <div className="audit-filter-actions">
            <button className="btn btn-primary" onClick={handleFilter}>
              Apply Filters
            </button>
            <button className="btn" onClick={handleClearFilters}>
              Clear
            </button>
            <button className="btn" onClick={handleExport}>
              Export CSV
            </button>
            <label className="audit-auto-refresh">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
              />
              Auto-refresh
            </label>
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="card">
        <div className="result-header">
          <h3>Audit Entries ({total})</h3>
          <div className="audit-pagination">
            <button
              className="btn btn-sm"
              disabled={page <= 1}
              onClick={() => setPage(p => p - 1)}
            >
              Previous
            </button>
            <span className="text-dim">
              Page {page} of {totalPages}
            </span>
            <button
              className="btn btn-sm"
              disabled={page >= totalPages}
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </button>
          </div>
        </div>

        {loading ? (
          <p className="loading">Loading audit entries...</p>
        ) : entries.length === 0 ? (
          <p className="text-dim">No audit entries found.</p>
        ) : (
          <div className="audit-table">
            <div className="audit-table-header">
              <span>Timestamp</span>
              <span>User</span>
              <span>Action</span>
              <span>Resource</span>
              <span>IP Address</span>
              <span>Details</span>
            </div>
            {entries.map((entry, i) => (
              <div key={entry.id ?? i} className="audit-table-row">
                <span className="audit-cell-timestamp">
                  {entry.created_at}
                </span>
                <span className="audit-cell-user">
                  {entry.username || entry.user_id}
                </span>
                <span>
                  <span className={`audit-action-badge audit-action-${entry.action}`}>
                    {entry.action}
                  </span>
                </span>
                <span className="audit-cell-resource">
                  {entry.resource_type}
                  {entry.resource_id ? ` / ${entry.resource_id}` : ''}
                </span>
                <span className="audit-cell-ip">
                  {entry.ip_address || '-'}
                </span>
                <span className="audit-cell-details text-dim">
                  {entry.details || '-'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
