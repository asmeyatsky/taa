import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../auth/AuthContext'

interface Organization {
  id: string
  name: string
  slug: string
  plan: 'free' | 'pro' | 'enterprise'
  max_users: number
  is_active: boolean
  created_at: string
}

interface OrgUser {
  id: string
  username: string
  name: string
  email: string
  role: string
}

interface InviteForm {
  username: string
  name: string
  email: string
  role: string
  password: string
}

const PLAN_LABELS: Record<string, string> = {
  free: 'Free',
  pro: 'Pro',
  enterprise: 'Enterprise',
}

const PLAN_COLORS: Record<string, string> = {
  free: '#6b7280',
  pro: '#3b82f6',
  enterprise: '#8b5cf6',
}

export default function OrganizationPage() {
  const { token } = useAuth()
  const [orgs, setOrgs] = useState<Organization[]>([])
  const [selectedOrg, setSelectedOrg] = useState<Organization | null>(null)
  const [orgUsers, setOrgUsers] = useState<OrgUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState<InviteForm>({
    username: '',
    name: '',
    email: '',
    role: 'user',
    password: '',
  })
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '',
    slug: '',
    plan: 'free',
    max_users: 5,
  })

  const headers = useCallback(() => {
    const h: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) h['Authorization'] = `Bearer ${token}`
    return h
  }, [token])

  const fetchOrgs = useCallback(async () => {
    try {
      setLoading(true)
      const res = await fetch('/api/orgs/', { headers: headers() })
      if (!res.ok) throw new Error('Failed to load organizations')
      const data = await res.json()
      setOrgs(data)
      if (data.length > 0 && !selectedOrg) {
        setSelectedOrg(data[0])
      }
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [headers, selectedOrg])

  const fetchOrgUsers = useCallback(async (orgId: string) => {
    try {
      const res = await fetch(`/api/orgs/${orgId}/users`, { headers: headers() })
      if (!res.ok) throw new Error('Failed to load users')
      const data = await res.json()
      setOrgUsers(data)
    } catch (err: any) {
      setError(err.message)
    }
  }, [headers])

  useEffect(() => {
    fetchOrgs()
  }, [])

  useEffect(() => {
    if (selectedOrg) {
      fetchOrgUsers(selectedOrg.id)
    }
  }, [selectedOrg, fetchOrgUsers])

  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await fetch('/api/orgs/', {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(createForm),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to create organization')
      }
      const newOrg = await res.json()
      setOrgs(prev => [...prev, newOrg])
      setSelectedOrg(newOrg)
      setShowCreate(false)
      setCreateForm({ name: '', slug: '', plan: 'free', max_users: 5 })
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleInviteUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedOrg) return
    try {
      const res = await fetch(`/api/orgs/${selectedOrg.id}/invite`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(inviteForm),
      })
      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to invite user')
      }
      await fetchOrgUsers(selectedOrg.id)
      setShowInvite(false)
      setInviteForm({ username: '', name: '', email: '', role: 'user', password: '' })
    } catch (err: any) {
      setError(err.message)
    }
  }

  const handleUpdateOrg = async (fields: Partial<Organization>) => {
    if (!selectedOrg) return
    try {
      const res = await fetch(`/api/orgs/${selectedOrg.id}`, {
        method: 'PUT',
        headers: headers(),
        body: JSON.stringify(fields),
      })
      if (!res.ok) throw new Error('Failed to update organization')
      const updated = await res.json()
      setSelectedOrg(updated)
      setOrgs(prev => prev.map(o => o.id === updated.id ? updated : o))
    } catch (err: any) {
      setError(err.message)
    }
  }

  if (loading) {
    return <div className="page-loading">Loading organizations...</div>
  }

  return (
    <div className="org-page">
      <div className="page-header">
        <h2>Organizations</h2>
        <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
          + New Organization
        </button>
      </div>

      {error && (
        <div className="alert alert-error" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <div className="org-layout">
        {/* Org Switcher sidebar */}
        <div className="org-sidebar">
          <h3>All Organizations</h3>
          <div className="org-list">
            {orgs.map(org => (
              <div
                key={org.id}
                className={`org-item ${selectedOrg?.id === org.id ? 'active' : ''}`}
                onClick={() => setSelectedOrg(org)}
              >
                <div className="org-item-name">{org.name}</div>
                <div className="org-item-meta">
                  <span
                    className="plan-badge"
                    style={{ backgroundColor: PLAN_COLORS[org.plan] || '#6b7280' }}
                  >
                    {PLAN_LABELS[org.plan] || org.plan}
                  </span>
                  {!org.is_active && <span className="status-inactive">Inactive</span>}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Org details */}
        <div className="org-detail">
          {selectedOrg ? (
            <>
              <div className="org-settings card">
                <h3>Settings</h3>
                <div className="settings-grid">
                  <div className="setting-item">
                    <label>Name</label>
                    <span>{selectedOrg.name}</span>
                  </div>
                  <div className="setting-item">
                    <label>Slug</label>
                    <span>{selectedOrg.slug}</span>
                  </div>
                  <div className="setting-item">
                    <label>Plan</label>
                    <select
                      value={selectedOrg.plan}
                      onChange={e => handleUpdateOrg({ plan: e.target.value } as any)}
                    >
                      <option value="free">Free</option>
                      <option value="pro">Pro</option>
                      <option value="enterprise">Enterprise</option>
                    </select>
                  </div>
                  <div className="setting-item">
                    <label>Max Users</label>
                    <span>{selectedOrg.max_users}</span>
                  </div>
                  <div className="setting-item">
                    <label>Status</label>
                    <span>{selectedOrg.is_active ? 'Active' : 'Inactive'}</span>
                  </div>
                  <div className="setting-item">
                    <label>Created</label>
                    <span>{selectedOrg.created_at}</span>
                  </div>
                </div>
              </div>

              <div className="org-members card">
                <div className="card-header">
                  <h3>Members ({orgUsers.length}/{selectedOrg.max_users})</h3>
                  <button className="btn btn-sm" onClick={() => setShowInvite(true)}>
                    + Invite User
                  </button>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Username</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orgUsers.map(u => (
                      <tr key={u.id}>
                        <td>{u.username}</td>
                        <td>{u.name}</td>
                        <td>{u.email}</td>
                        <td>
                          <span className={`role-badge role-${u.role}`}>{u.role}</span>
                        </td>
                      </tr>
                    ))}
                    {orgUsers.length === 0 && (
                      <tr>
                        <td colSpan={4} style={{ textAlign: 'center', color: '#999' }}>
                          No members yet
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="empty-state">Select an organization to view details</div>
          )}
        </div>
      </div>

      {/* Create org modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={() => setShowCreate(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Create Organization</h3>
            <form onSubmit={handleCreateOrg}>
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={e => setCreateForm(f => ({ ...f, name: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label>Slug (URL-friendly identifier)</label>
                <input
                  type="text"
                  value={createForm.slug}
                  onChange={e => setCreateForm(f => ({ ...f, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') }))}
                  required
                  pattern="^[a-z0-9][a-z0-9\-]*$"
                />
              </div>
              <div className="form-group">
                <label>Plan</label>
                <select
                  value={createForm.plan}
                  onChange={e => setCreateForm(f => ({ ...f, plan: e.target.value }))}
                >
                  <option value="free">Free</option>
                  <option value="pro">Pro</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </div>
              <div className="form-group">
                <label>Max Users</label>
                <input
                  type="number"
                  min={1}
                  max={1000}
                  value={createForm.max_users}
                  onChange={e => setCreateForm(f => ({ ...f, max_users: parseInt(e.target.value) || 5 }))}
                />
              </div>
              <div className="form-actions">
                <button type="button" className="btn" onClick={() => setShowCreate(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Create</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Invite user modal */}
      {showInvite && (
        <div className="modal-overlay" onClick={() => setShowInvite(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Invite User to {selectedOrg?.name}</h3>
            <form onSubmit={handleInviteUser}>
              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  value={inviteForm.username}
                  onChange={e => setInviteForm(f => ({ ...f, username: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label>Name</label>
                <input
                  type="text"
                  value={inviteForm.name}
                  onChange={e => setInviteForm(f => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label>Email</label>
                <input
                  type="email"
                  value={inviteForm.email}
                  onChange={e => setInviteForm(f => ({ ...f, email: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label>Role</label>
                <select
                  value={inviteForm.role}
                  onChange={e => setInviteForm(f => ({ ...f, role: e.target.value }))}
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="management">Management</option>
                </select>
              </div>
              <div className="form-group">
                <label>Password</label>
                <input
                  type="password"
                  value={inviteForm.password}
                  onChange={e => setInviteForm(f => ({ ...f, password: e.target.value }))}
                  required
                  minLength={6}
                />
              </div>
              <div className="form-actions">
                <button type="button" className="btn" onClick={() => setShowInvite(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Invite</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
