import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { MantineProvider, createTheme } from '@mantine/core'
import { Notifications } from '@mantine/notifications'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import '@mantine/core/styles.css'
import '@mantine/notifications/styles.css'
import '@mantine/carousel/styles.css'
import './styles.css'
import { AuthProvider } from './context/AuthContext'
import { FavoriteGroupProvider } from './context/FavoriteGroupContext'
import { UnseenReviewsProvider } from './context/UnseenReviewsContext'
import { PlayerProvider } from './context/PlayerContext'
import { ChatSocketProvider } from './context/ChatSocketContext'
import { ApiError } from './services/apiClient'
import App from './App'

const theme = createTheme({
  primaryColor: 'violet',
  fontFamily: 'Inter, system-ui, sans-serif',
})

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // Retrying a 401 without credentials can never succeed — settle
      // immediately so callers (e.g. anonymous-viewing redirects) see the
      // error without waiting on a pointless retry/backoff cycle.
      retry: (failureCount, error) =>
        error instanceof ApiError && error.status === 401 ? false : failureCount < 1,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <Notifications position="top-right" />
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          {/* Inside AuthProvider (needs the session) and the QueryClient (writes
              incoming messages into the cache). One socket for the whole app. */}
          <ChatSocketProvider>
            <FavoriteGroupProvider>
              <UnseenReviewsProvider>
                <PlayerProvider>
                  <App />
                </PlayerProvider>
              </UnseenReviewsProvider>
            </FavoriteGroupProvider>
          </ChatSocketProvider>
        </AuthProvider>
      </QueryClientProvider>
    </MantineProvider>
  </StrictMode>,
)
