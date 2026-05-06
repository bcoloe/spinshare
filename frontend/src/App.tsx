import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { LoadingOverlay } from '@mantine/core'
import { useAuth } from './hooks/useAuth'

const ProtectedRoute = lazy(() => import('./components/auth/ProtectedRoute'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))

function RootRoute() {
  const { user } = useAuth()
  const favoriteId = user?.username
    ? localStorage.getItem(`spinshare_favorite_group_${user.username}`)
    : null
  if (favoriteId) return <Navigate to={`/groups/${favoriteId}`} replace />
  return <DashboardPage />
}
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const GroupPage = lazy(() => import('./pages/GroupPage'))
const GroupCatalogPage = lazy(() => import('./pages/GroupCatalogPage'))
const GroupSettingsPage = lazy(() => import('./pages/GroupSettingsPage'))
const DailySpinPage = lazy(() => import('./pages/DailySpinPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const InviteAcceptPage = lazy(() => import('./pages/InviteAcceptPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const UserProfilePage = lazy(() => import('./pages/UserProfilePage'))
const AlbumPage = lazy(() => import('./pages/AlbumPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/invite/:token', element: <InviteAcceptPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/', element: <RootRoute /> },
      { path: '/groups/:groupId', element: <GroupPage /> },
      { path: '/groups/:groupId/spin', element: <DailySpinPage /> },
      { path: '/groups/:groupId/catalog', element: <GroupCatalogPage /> },
      { path: '/groups/:groupId/settings', element: <GroupSettingsPage /> },
      { path: '/profile', element: <ProfilePage /> },
      { path: '/users/:username', element: <UserProfilePage /> },
      { path: '/albums/:albumId', element: <AlbumPage /> },
      { path: '/search', element: <SearchPage /> },
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
