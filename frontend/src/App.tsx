import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom'
import { LoadingOverlay } from '@mantine/core'
import { useAuth } from './hooks/useAuth'
import ChunkErrorBoundary from './components/ChunkErrorBoundary'

const ProtectedRoute = lazy(() => import('./components/auth/ProtectedRoute'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const LandingPage = lazy(() => import('./pages/LandingPage'))

function RootRoute() {
  const { user, isInitializing } = useAuth()
  if (isInitializing) return <LoadingOverlay visible />
  if (!user) return <LandingPage />
  const favoriteId = localStorage.getItem(`spinshare_favorite_group_${user.username}`)
  if (favoriteId) return <Navigate to={`/groups/${favoriteId}`} replace />
  return <DashboardPage />
}
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage'))
const GroupPage = lazy(() => import('./pages/GroupPage'))
const GroupCatalogPage = lazy(() => import('./pages/GroupCatalogPage'))
const GroupSettingsPage = lazy(() => import('./pages/GroupSettingsPage'))
const DailySpinPage = lazy(() => import('./pages/DailySpinPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const InviteAcceptPage = lazy(() => import('./pages/InviteAcceptPage'))
const JoinGroupPage = lazy(() => import('./pages/JoinGroupPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const UserProfilePage = lazy(() => import('./pages/UserProfilePage'))
const AlbumPage = lazy(() => import('./pages/AlbumPage'))
const ArtistPage = lazy(() => import('./pages/ArtistPage'))
const SearchPage = lazy(() => import('./pages/SearchPage'))
const ExploreAlbumsPage = lazy(() => import('./pages/explore/ExploreAlbumsPage'))
const ExploreGroupsPage = lazy(() => import('./pages/explore/ExploreGroupsPage'))
const ExploreUsersPage = lazy(() => import('./pages/explore/ExploreUsersPage'))
const ExploreStatsPage = lazy(() => import('./pages/explore/ExploreStatsPage'))
const AboutPage = lazy(() => import('./pages/AboutPage'))
const GettingStartedPage = lazy(() => import('./pages/GettingStartedPage'))
const ContributingPage = lazy(() => import('./pages/ContributingPage'))

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/forgot-password', element: <ForgotPasswordPage /> },
  { path: '/reset-password', element: <ResetPasswordPage /> },
  { path: '/invite/:token', element: <InviteAcceptPage /> },
  { path: '/join/:token', element: <JoinGroupPage /> },
  { path: '/', element: <RootRoute /> },
  { path: '/about', element: <AboutPage /> },
  { path: '/about/getting-started', element: <GettingStartedPage /> },
  { path: '/about/contributing', element: <ContributingPage /> },
  // GroupPage handles its own anonymous-viewing logic (global/bot groups only)
  // and redirects to /login itself, so it stays outside ProtectedRoute.
  { path: '/groups/:groupId', element: <GroupPage /> },
  // Albums, groups, and stats browsing are publicly readable; user browsing
  // stays behind login (see /explore/users below).
  { path: '/albums/:albumId', element: <AlbumPage /> },
  { path: '/artists/:artistName', element: <ArtistPage /> },
  { path: '/explore', element: <Navigate to="/explore/albums" replace /> },
  { path: '/explore/albums', element: <ExploreAlbumsPage /> },
  { path: '/explore/groups', element: <ExploreGroupsPage /> },
  { path: '/explore/stats', element: <ExploreStatsPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/groups/:groupId/spin', element: <DailySpinPage /> },
      { path: '/groups/:groupId/catalog', element: <GroupCatalogPage /> },
      { path: '/groups/:groupId/settings', element: <GroupSettingsPage /> },
      { path: '/profile', element: <ProfilePage /> },
      { path: '/users/:username', element: <UserProfilePage /> },
      { path: '/search', element: <SearchPage /> },
      { path: '/explore/users', element: <ExploreUsersPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

export default function App() {
  return (
    <ChunkErrorBoundary>
      <Suspense fallback={<LoadingOverlay visible />}>
        <RouterProvider router={router} />
      </Suspense>
    </ChunkErrorBoundary>
  )
}
