import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { DEMO_USERS, ROLE_LABELS } from '../auth/types'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleLogin = (userId: string) => {
    login(userId)
    navigate('/')
  }

  return (
    <div className="login-page">
      <div className="login-container">
        <div className="login-brand">
          <h1>TAA</h1>
          <p>Telco Analytics Accelerator</p>
        </div>
        <div className="login-card">
          <h2>Sign In</h2>
          <p className="login-desc">Select a role to explore the platform</p>
          <div className="login-users">
            {DEMO_USERS.map(u => (
              <button
                key={u.id}
                className="login-user-btn"
                onClick={() => handleLogin(u.id)}
              >
                <div className="login-user-avatar">
                  {u.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div className="login-user-info">
                  <span className="login-user-name">{u.name}</span>
                  <span className="login-user-email">{u.email}</span>
                </div>
                <span className={`role-badge role-${u.role}`}>
                  {ROLE_LABELS[u.role]}
                </span>
              </button>
            ))}
          </div>
        </div>
        <p className="login-footer">
          Demo authentication — select any user to explore role-based access controls
        </p>
      </div>
    </div>
  )
}
