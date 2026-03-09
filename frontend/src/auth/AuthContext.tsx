import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react'
import { ROLE_PERMISSIONS, type User, type Role, type Permission } from './types'

interface AuthContextValue {
  user: User | null
  token: string | null
  login: (username: string, password: string) => Promise<boolean>
  loginDemo: (userId: string) => void
  logout: () => void
  switchRole: (role: Role) => void
  hasPermission: (permission: Permission) => boolean
  hasAnyPermission: (...permissions: Permission[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

const TOKEN_KEY = 'taa_token'
const USER_KEY = 'taa_user'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const saved = localStorage.getItem(USER_KEY)
    return saved ? JSON.parse(saved) : null
  })
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY)
  )

  // Persist to localStorage
  useEffect(() => {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
    else localStorage.removeItem(USER_KEY)
  }, [user])

  useEffect(() => {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  }, [token])

  // Validate token on mount
  useEffect(() => {
    if (token) {
      fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => {
        if (!r.ok) {
          setToken(null)
          setUser(null)
        }
      }).catch(() => {
        // Server not reachable, keep session for demo mode
      })
    }
  }, [])

  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    try {
      const res = await fetch('/api/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username, password }),
      })
      if (!res.ok) return false
      const data = await res.json()
      setToken(data.access_token)
      setUser({
        id: data.user.id,
        name: data.user.name,
        email: data.user.email,
        role: data.user.role as Role,
      })
      return true
    } catch {
      return false
    }
  }, [])

  const loginDemo = useCallback((userId: string) => {
    // Quick demo login mapping
    const demoUsers: Record<string, { user: User; username: string; password: string }> = {
      '1': { user: { id: '1', name: 'Alex Analyst', email: 'alex@telco.com', role: 'user' }, username: 'alex', password: 'analyst123' },
      '2': { user: { id: '2', name: 'Sarah Admin', email: 'sarah@telco.com', role: 'admin' }, username: 'sarah', password: 'admin123' },
      '3': { user: { id: '3', name: 'Mike Director', email: 'mike@telco.com', role: 'management' }, username: 'mike', password: 'director123' },
    }
    const demo = demoUsers[userId]
    if (demo) {
      // Try JWT login first, fall back to demo mode
      login(demo.username, demo.password).then(success => {
        if (!success) {
          // Fallback: set user without token (demo mode)
          setUser(demo.user)
          setToken(null)
        }
      })
    }
  }, [login])

  const logout = useCallback(() => {
    setUser(null)
    setToken(null)
  }, [])

  const switchRole = useCallback((role: Role) => {
    if (user) setUser({ ...user, role })
  }, [user])

  const hasPermission = useCallback((permission: Permission): boolean => {
    if (!user) return false
    return ROLE_PERMISSIONS[user.role].includes(permission)
  }, [user])

  const hasAnyPermission = useCallback((...permissions: Permission[]): boolean => {
    if (!user) return false
    return permissions.some(p => ROLE_PERMISSIONS[user.role].includes(p))
  }, [user])

  return (
    <AuthContext.Provider value={{ user, token, login, loginDemo, logout, switchRole, hasPermission, hasAnyPermission }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
