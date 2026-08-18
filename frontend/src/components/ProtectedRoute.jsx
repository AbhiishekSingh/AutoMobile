import { Navigate } from 'react-router-dom'
import { useAuth, ROLE_HOME } from '../lib/auth'

// Guards a route: must be logged in, and (optionally) have one of `roles`.
export default function ProtectedRoute({ roles, children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (roles && !roles.includes(user.role)) {
    return <Navigate to={ROLE_HOME[user.role] || '/login'} replace />
  }
  return children
}
