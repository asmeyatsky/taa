import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { DEMO_USERS, ROLE_LABELS } from '../auth/types'

export default function LoginPage() {
  const { login, loginDemo } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'demo' | 'credentials'>('demo')

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const success = await login(username, password)
    setLoading(false)
    if (success) {
      navigate('/')
    } else {
      setError('Invalid username or password')
    }
  }

  const handleDemoLogin = (userId: string) => {
    loginDemo(userId)
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

          <div className="login-mode-tabs">
            <button
              className={`login-mode-tab ${mode === 'demo' ? 'login-mode-active' : ''}`}
              onClick={() => setMode('demo')}
            >
              Demo Users
            </button>
            <button
              className={`login-mode-tab ${mode === 'credentials' ? 'login-mode-active' : ''}`}
              onClick={() => setMode('credentials')}
            >
              Credentials
            </button>
          </div>

          {mode === 'demo' ? (
            <>
              <p className="login-desc">Select a role to explore the platform</p>
              <div className="login-users">
                {DEMO_USERS.map(u => (
                  <button
                    key={u.id}
                    className="login-user-btn"
                    onClick={() => handleDemoLogin(u.id)}
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
            </>
          ) : (
            <form onSubmit={handleLogin} className="login-form">
              <div className="form-field">
                <label htmlFor="username">Username</label>
                <input
                  id="username"
                  className="input"
                  type="text"
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="alex, sarah, or mike"
                  autoComplete="username"
                />
              </div>
              <div className="form-field">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  className="input"
                  type="password"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="Enter password"
                  autoComplete="current-password"
                />
              </div>
              {error && <div className="login-error">{error}</div>}
              <button
                type="submit"
                className="btn btn-primary btn-lg"
                style={{ width: '100%' }}
                disabled={loading || !username || !password}
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
              <div className="login-hint">
                Demo credentials: alex/analyst123, sarah/admin123, mike/director123
              </div>
            </form>
          )}
        </div>
        <p className="login-footer">
          {mode === 'demo'
            ? 'Demo authentication \u2014 select any user to explore role-based access controls'
            : 'JWT authentication with bcrypt password hashing'
          }
        </p>
      </div>
    </div>
  )
}
