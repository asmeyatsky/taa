import { useState } from 'react'
import { DEMO_USERS, ROLE_LABELS, ROLE_PERMISSIONS, type Role } from '../auth/types'

export default function UsersPage() {
  const [users] = useState(DEMO_USERS)
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)

  return (
    <div className="page">
      <h2>User Management</h2>
      <p className="page-desc">
        Manage platform users and role-based access controls. Only Management users can access this page.
      </p>

      <section className="card">
        <h3>Active Users</h3>
        <div className="users-grid">
          <div className="users-header">
            <span>Name</span>
            <span>Email</span>
            <span>Role</span>
            <span>Permissions</span>
          </div>
          {users.map(u => (
            <div key={u.id} className="users-row">
              <span className="user-cell-name">{u.name}</span>
              <span className="user-cell-email">{u.email}</span>
              <span>
                <span className={`role-badge role-${u.role}`}>{ROLE_LABELS[u.role]}</span>
              </span>
              <span className="user-cell-perms">{ROLE_PERMISSIONS[u.role].length} permissions</span>
            </div>
          ))}
        </div>
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
    </div>
  )
}
