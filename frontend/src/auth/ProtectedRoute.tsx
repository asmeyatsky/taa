import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext'
import type { Permission } from './types'

interface Props {
  children: React.ReactNode
  permission?: Permission
  anyPermission?: Permission[]
  fallback?: React.ReactNode
}

export default function ProtectedRoute({ children, permission, anyPermission, fallback }: Props) {
  const { user, hasPermission, hasAnyPermission } = useAuth()

  if (!user) return <Navigate to="/login" replace />

  if (permission && !hasPermission(permission)) {
    return fallback ? <>{fallback}</> : <AccessDenied />
  }

  if (anyPermission && !hasAnyPermission(...anyPermission)) {
    return fallback ? <>{fallback}</> : <AccessDenied />
  }

  return <>{children}</>
}

function AccessDenied() {
  return (
    <div className="page">
      <div className="access-denied">
        <h2>Access Denied</h2>
        <p>You do not have permission to view this page. Contact your administrator to request access.</p>
      </div>
    </div>
  )
}
