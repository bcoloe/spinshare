import { createContext, useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { configureApiClient, refreshAccessToken, RefreshAuthError } from '../services/apiClient'
import { authService } from '../services/authService'
import type { LoginRequest, UserResponse } from '../types/auth'

interface AuthContextValue {
  user: UserResponse | null
  isInitializing: boolean
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)
  const accessTokenRef = useRef<string | null>(null)

  const logout = useCallback(() => {
    accessTokenRef.current = null
    localStorage.removeItem('refresh_token')
    setUser(null)
  }, [])

  // Wire up the apiClient with the token getter and unauthorized handler.
  // This runs once on mount before any fetch can happen.
  useEffect(() => {
    configureApiClient(
      () => accessTokenRef.current,
      logout,
    )
  }, [logout])

  // Listen for token refreshes triggered inside apiClient (on 401 retry)
  useEffect(() => {
    const handler = (e: Event) => {
      accessTokenRef.current = (e as CustomEvent<string>).detail
    }
    window.addEventListener('token:refreshed', handler)
    return () => window.removeEventListener('token:refreshed', handler)
  }, [])

  // Silent re-auth on mount using stored refresh token.
  // Uses the shared refreshAccessToken() from apiClient so this call and any
  // concurrent 401 retries deduplicate into a single refresh request.
  useEffect(() => {
    if (!localStorage.getItem('refresh_token')) {
      setIsInitializing(false)
      return
    }

    refreshAccessToken()
      .then((newToken) => {
        if (!newToken) return undefined  // transient failure: keep token, don't set user
        accessTokenRef.current = newToken
        return authService.getMe()
      })
      .then((me) => { if (me) setUser(me) })
      .catch((err) => {
        if (err instanceof RefreshAuthError) {
          // Token is genuinely invalid — clear it so the login page is shown.
          localStorage.removeItem('refresh_token')
        }
        // Any other error (5xx, network, getMe failure) is transient: keep the
        // refresh token so the next page load can try again without forcing re-login.
      })
      .finally(() => setIsInitializing(false))
  }, [])

  const login = useCallback(async (credentials: LoginRequest) => {
    const res = await authService.login(credentials)
    accessTokenRef.current = res.access_token
    localStorage.setItem('refresh_token', res.refresh_token)
    setUser(res.user)
  }, [])

  const refreshUser = useCallback(async () => {
    const updated = await authService.getMe()
    setUser(updated)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isInitializing, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}
