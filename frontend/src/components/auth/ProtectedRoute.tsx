import { Navigate, Outlet } from 'react-router-dom'
import { LoadingOverlay } from '@mantine/core'
import { useAuth } from '../../hooks/useAuth'

export default function ProtectedRoute() {
  const { user, isInitializing } = useAuth()

  if (isInitializing) return <LoadingOverlay visible />
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}
