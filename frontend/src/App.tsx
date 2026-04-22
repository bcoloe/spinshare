import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { LoadingOverlay } from '@mantine/core'

const ProtectedRoute = lazy(() => import('./components/auth/ProtectedRoute'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const GroupPage = lazy(() => import('./pages/GroupPage'))
const GroupCatalogPage = lazy(() => import('./pages/GroupCatalogPage'))
const GroupSettingsPage = lazy(() => import('./pages/GroupSettingsPage'))
const DailySpinPage = lazy(() => import('./pages/DailySpinPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const InviteAcceptPage = lazy(() => import('./pages/InviteAcceptPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/invite/:token', element: <InviteAcceptPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/groups/:groupId', element: <GroupPage /> },
      { path: '/groups/:groupId/spin', element: <DailySpinPage /> },
      { path: '/groups/:groupId/catalog', element: <GroupCatalogPage /> },
      { path: '/groups/:groupId/settings', element: <GroupSettingsPage /> },
      { path: '/profile', element: <ProfilePage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

export default function App() {
  return (
    <Suspense fallback={<LoadingOverlay visible />}>
      <RouterProvider router={router} />
    </Suspense>
  )
}
