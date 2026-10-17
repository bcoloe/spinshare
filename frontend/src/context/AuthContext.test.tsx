import { act, render } from '@testing-library/react'
import { useContext } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { draftStorageKey } from '../utils/draftStorage'

const handlers: { unauthorized?: () => void } = {}
vi.mock('../services/apiClient', () => ({
  configureApiClient: (_getToken: unknown, onUnauthorized: () => void) => { handlers.unauthorized = onUnauthorized },
  refreshAccessToken: vi.fn(),
  RefreshAuthError: class extends Error {},
}))
vi.mock('../services/authService', () => ({ authService: {} }))

import { AuthContext, AuthProvider } from './AuthContext'

function renderProvider() {
  const ctx: { logout?: () => void } = {}
  function Probe() {
    ctx.logout = useContext(AuthContext)!.logout
    return null
  }
  render(<AuthProvider><Probe /></AuthProvider>)
  return ctx
}

const DRAFT = draftStorageKey(7, 42)

describe('ending a session', () => {
  beforeEach(() => {
    localStorage.clear()
    localStorage.setItem(DRAFT, '{"comment":"unsent"}')
  })

  it('an expired or revoked session keeps local review drafts', () => {
    renderProvider()
    localStorage.setItem('refresh_token', 'stale')

    act(() => handlers.unauthorized!())

    expect(localStorage.getItem('refresh_token')).toBeNull()
    expect(localStorage.getItem(DRAFT)).not.toBeNull()
  })

  it('a deliberate logout forgets them', () => {
    const ctx = renderProvider()
    act(() => ctx.logout!())
    expect(localStorage.getItem(DRAFT)).toBeNull()
  })
})
