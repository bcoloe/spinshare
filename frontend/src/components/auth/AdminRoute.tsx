import { Navigate, Outlet } from 'react-router-dom'
import { LoadingOverlay } from '@mantine/core'
import { useAuth } from '../../hooks/useAuth'

/**
 * Site-admin route guard (users.is_admin), not the per-group role of the same name.
 *
 * Handles isInitializing itself rather than nesting inside ProtectedRoute, so a
 * hard refresh on /admin waits for auth to resolve instead of bouncing to login.
 */
export default function AdminRoute() {
  const { user, isInitializing } = useAuth()

  if (isInitializing) return <LoadingOverlay visible />
  if (!user) return <Navigate to="/login" replace />
  if (!user.is_admin) return <Navigate to="/" replace />
  return <Outlet />
}
