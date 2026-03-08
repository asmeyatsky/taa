import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ROLE_LABELS, type Permission } from '../auth/types'

interface NavItem {
  to: string
  label: string
  icon: string
  permission?: Permission
}

const navItems: NavItem[] = [
  { to: '/', label: 'Home', icon: '\u2302' },
  { to: '/generate', label: 'Generate', icon: '\u26A1' },
  { to: '/domains', label: 'Domains', icon: '\u2637' },
  { to: '/compliance', label: 'Compliance', icon: '\u2616' },
  { to: '/analytics', label: 'Analytics', icon: '\u2197' },
  { to: '/users', label: 'Users', icon: '\u2699', permission: 'users:manage' },
]

export default function Layout() {
  const { user, logout, hasPermission } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const visibleNav = navItems.filter(
    item => !item.permission || hasPermission(item.permission)
  )

  return (
    <div className="app-layout">
      <header className="app-header">
        <NavLink to="/" className="header-brand">
          <h1>TAA</h1>
          <span className="header-subtitle">Telco Analytics Accelerator</span>
        </NavLink>
        {user && (
          <div className="header-user">
            <span className={`role-badge role-${user.role}`}>
              {ROLE_LABELS[user.role]}
            </span>
            <span className="user-name">{user.name}</span>
            <button className="btn btn-sm" onClick={handleLogout}>
              Sign Out
            </button>
          </div>
        )}
      </header>
      <div className="app-body">
        <nav className="app-sidebar">
          {visibleNav.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
