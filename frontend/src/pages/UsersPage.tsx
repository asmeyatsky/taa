import { useEffect, useState, useCallback } from 'react'
import { ROLE_LABELS, ROLE_PERMISSIONS, type Role } from '../auth/types'
import { api, type ApiUser, type CreateUserRequest, type UpdateUserRequest } from '../api/client'

type ModalMode = 'create' | 'edit' | 'reset-password' | 'confirm-delete' | null

export default function UsersPage() {
  const [users, setUsers] = useState<ApiUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)

  // Modal state
  const [modalMode, setModalMode] = useState<ModalMode>(null)
  const [selectedUser, setSelectedUser] = useState<ApiUser | null>(null)

  // Form state
  const [formUsername, setFormUsername] = useState('')
  const [formName, setFormName] = useState('')
  const [formEmail, setFormEmail] = useState('')
  const [formRole, setFormRole] = useState<string>('user')
  const [formPassword, setFormPassword] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [formSubmitting, setFormSubmitting] = useState(false)

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await api.getUsers()
      setUsers(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadUsers()
  }, [loadUsers])

  const openCreate = () => {
    setFormUsername('')
    setFormName('')
    setFormEmail('')
    setFormRole('user')
    setFormPassword('')
    setFormError(null)
    setSelectedUser(null)
    setModalMode('create')
  }

  const openEdit = (user: ApiUser) => {
    setFormName(user.name)
    setFormEmail(user.email)
    setFormRole(user.role)
    setFormPassword('')
    setFormError(null)
    setSelectedUser(user)
    setModalMode('edit')
  }

  const openResetPassword = (user: ApiUser) => {
    setFormPassword('')
    setFormError(null)
    setSelectedUser(user)
    setModalMode('reset-password')
  }

  const openDelete = (user: ApiUser) => {
    setFormError(null)
    setSelectedUser(user)
    setModalMode('confirm-delete')
  }

  const closeModal = () => {
    setModalMode(null)
    setSelectedUser(null)
    setFormError(null)
  }

  const handleCreate = async () => {
    if (!formUsername.trim()) {
      setFormError('Username is required')
      return
    }
    if (!formPassword.trim()) {
      setFormError('Password is required')
      return
    }
    setFormSubmitting(true)
    setFormError(null)
    try {
      const req: CreateUserRequest = {
        username: formUsername.trim(),
        name: formName.trim(),
        email: formEmail.trim(),
        role: formRole,
        password: formPassword,
      }
      await api.createUser(req)
      closeModal()
      await loadUsers()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to create user')
    } finally {
      setFormSubmitting(false)
    }
  }

  const handleUpdate = async () => {
    if (!selectedUser) return
    setFormSubmitting(true)
    setFormError(null)
    try {
      const req: UpdateUserRequest = {
        name: formName.trim(),
        email: formEmail.trim(),
        role: formRole,
      }
      if (formPassword.trim()) {
        req.password = formPassword
      }
      await api.updateUser(selectedUser.id, req)
      closeModal()
      await loadUsers()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to update user')
    } finally {
      setFormSubmitting(false)
    }
  }

  const handleResetPassword = async () => {
    if (!selectedUser) return
    if (!formPassword.trim()) {
      setFormError('New password is required')
      return
    }
    setFormSubmitting(true)
    setFormError(null)
    try {
      await api.resetPassword(selectedUser.id, formPassword)
      closeModal()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to reset password')
    } finally {
      setFormSubmitting(false)
    }
  }

  const handleDelete = async () => {
    if (!selectedUser) return
    setFormSubmitting(true)
    setFormError(null)
    try {
      await api.deleteUser(selectedUser.id)
      closeModal()
      await loadUsers()
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : 'Failed to delete user')
    } finally {
      setFormSubmitting(false)
    }
  }

  return (
    <div className="page">
      <h2>User Management</h2>
      <p className="page-desc">
        Manage platform users and role-based access controls. Only Management users can access this page.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <section className="card">
        <div className="users-card-header">
          <h3>Active Users</h3>
          <button className="btn btn-primary btn-sm" onClick={openCreate}>
            + Add User
          </button>
        </div>

        {loading ? (
          <p className="loading">Loading users...</p>
        ) : (
          <div className="users-grid">
            <div className="users-header users-header-actions">
              <span>Name</span>
              <span>Email</span>
              <span>Role</span>
              <span>Created</span>
              <span>Actions</span>
            </div>
            {users.map(u => (
              <div key={u.id} className="users-row users-row-actions">
                <span className="user-cell-name">
                  {u.name || u.username}
                  {u.disabled && <span className="badge badge-disabled">Disabled</span>}
                </span>
                <span className="user-cell-email">{u.email || '-'}</span>
                <span>
                  <span className={`role-badge role-${u.role}`}>
                    {ROLE_LABELS[u.role as Role] || u.role}
                  </span>
                </span>
                <span className="user-cell-date">
                  {u.created_at ? new Date(u.created_at + 'Z').toLocaleDateString() : '-'}
                </span>
                <span className="user-cell-actions">
                  <button className="btn btn-sm" onClick={() => openEdit(u)} title="Edit user">
                    Edit
                  </button>
                  <button className="btn btn-sm" onClick={() => openResetPassword(u)} title="Reset password">
                    Reset
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => openDelete(u)} title="Delete user">
                    Delete
                  </button>
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h3>Role Permissions Matrix</h3>
        <p className="page-desc" style={{ marginBottom: '1rem' }}>
          Click a role to see its permissions.
        </p>
        <div className="role-tabs">
          {(Object.keys(ROLE_LABELS) as Role[]).map(role => (
            <button
              key={role}
              className={`chip ${selectedRole === role ? 'chip-active' : ''}`}
              onClick={() => setSelectedRole(selectedRole === role ? null : role)}
            >
              {ROLE_LABELS[role]}
              <span className="chip-badge">{ROLE_PERMISSIONS[role].length}</span>
            </button>
          ))}
        </div>
        {selectedRole && (
          <div className="permissions-list">
            {ROLE_PERMISSIONS[selectedRole].map(perm => (
              <div key={perm} className="permission-item">
                <span className="permission-granted" />
                <span>{perm}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Modal overlay */}
      {modalMode && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            {modalMode === 'create' && (
              <>
                <h3 className="modal-title">Add New User</h3>
                {formError && <div className="alert alert-error">{formError}</div>}
                <div className="modal-form">
                  <div className="form-field">
                    <label>Username</label>
                    <input
                      className="input"
                      value={formUsername}
                      onChange={e => setFormUsername(e.target.value)}
                      placeholder="Enter username"
                      autoFocus
                    />
                  </div>
                  <div className="form-field">
                    <label>Full Name</label>
                    <input
                      className="input"
                      value={formName}
                      onChange={e => setFormName(e.target.value)}
                      placeholder="Enter full name"
                    />
                  </div>
                  <div className="form-field">
                    <label>Email</label>
                    <input
                      className="input"
                      type="email"
                      value={formEmail}
                      onChange={e => setFormEmail(e.target.value)}
                      placeholder="Enter email address"
                    />
                  </div>
                  <div className="form-field">
                    <label>Role</label>
                    <select
                      className="select"
                      value={formRole}
                      onChange={e => setFormRole(e.target.value)}
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                      <option value="management">Management</option>
                    </select>
                  </div>
                  <div className="form-field">
                    <label>Password</label>
                    <input
                      className="input"
                      type="password"
                      value={formPassword}
                      onChange={e => setFormPassword(e.target.value)}
                      placeholder="Enter password"
                    />
                  </div>
                </div>
                <div className="modal-actions">
                  <button className="btn" onClick={closeModal} disabled={formSubmitting}>
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleCreate}
                    disabled={formSubmitting}
                  >
                    {formSubmitting ? 'Creating...' : 'Create User'}
                  </button>
                </div>
              </>
            )}

            {modalMode === 'edit' && selectedUser && (
              <>
                <h3 className="modal-title">Edit User: {selectedUser.username}</h3>
                {formError && <div className="alert alert-error">{formError}</div>}
                <div className="modal-form">
                  <div className="form-field">
                    <label>Full Name</label>
                    <input
                      className="input"
                      value={formName}
                      onChange={e => setFormName(e.target.value)}
                      placeholder="Enter full name"
                      autoFocus
                    />
                  </div>
                  <div className="form-field">
                    <label>Email</label>
                    <input
                      className="input"
                      type="email"
                      value={formEmail}
                      onChange={e => setFormEmail(e.target.value)}
                      placeholder="Enter email address"
                    />
                  </div>
                  <div className="form-field">
                    <label>Role</label>
                    <select
                      className="select"
                      value={formRole}
                      onChange={e => setFormRole(e.target.value)}
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                      <option value="management">Management</option>
                    </select>
                  </div>
                  <div className="form-field">
                    <label>New Password (leave blank to keep current)</label>
                    <input
                      className="input"
                      type="password"
                      value={formPassword}
                      onChange={e => setFormPassword(e.target.value)}
                      placeholder="Enter new password"
                    />
                  </div>
                </div>
                <div className="modal-actions">
                  <button className="btn" onClick={closeModal} disabled={formSubmitting}>
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleUpdate}
                    disabled={formSubmitting}
                  >
                    {formSubmitting ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </>
            )}

            {modalMode === 'reset-password' && selectedUser && (
              <>
                <h3 className="modal-title">Reset Password: {selectedUser.username}</h3>
                {formError && <div className="alert alert-error">{formError}</div>}
                <div className="modal-form">
                  <div className="form-field">
                    <label>New Password</label>
                    <input
                      className="input"
                      type="password"
                      value={formPassword}
                      onChange={e => setFormPassword(e.target.value)}
                      placeholder="Enter new password"
                      autoFocus
                    />
                  </div>
                </div>
                <div className="modal-actions">
                  <button className="btn" onClick={closeModal} disabled={formSubmitting}>
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary"
                    onClick={handleResetPassword}
                    disabled={formSubmitting}
                  >
                    {formSubmitting ? 'Resetting...' : 'Reset Password'}
                  </button>
                </div>
              </>
            )}

            {modalMode === 'confirm-delete' && selectedUser && (
              <>
                <h3 className="modal-title">Delete User</h3>
                {formError && <div className="alert alert-error">{formError}</div>}
                <p className="modal-confirm-text">
                  Are you sure you want to delete <strong>{selectedUser.name || selectedUser.username}</strong>?
                  This action cannot be undone.
                </p>
                <div className="modal-actions">
                  <button className="btn" onClick={closeModal} disabled={formSubmitting}>
                    Cancel
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={handleDelete}
                    disabled={formSubmitting}
                  >
                    {formSubmitting ? 'Deleting...' : 'Delete User'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
