import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { ROLE_PERMISSIONS, DEMO_USERS, type User, type Role, type Permission } from './types'

interface AuthContextValue {
  user: User | null
  login: (userId: string) => void
  logout: () => void
  switchRole: (role: Role) => void
  hasPermission: (permission: Permission) => boolean
  hasAnyPermission: (...permissions: Permission[]) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)

  const login = useCallback((userId: string) => {
    const found = DEMO_USERS.find(u => u.id === userId)
    if (found) setUser(found)
  }, [])

  const logout = useCallback(() => setUser(null), [])

  const switchRole = useCallback((role: Role) => {
    if (user) {
      setUser({ ...user, role })
    }
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
    <AuthContext.Provider value={{ user, login, logout, switchRole, hasPermission, hasAnyPermission }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
