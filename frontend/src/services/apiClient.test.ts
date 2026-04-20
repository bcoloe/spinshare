import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiFetch, configureApiClient } from './apiClient'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('apiFetch', () => {
  beforeEach(() => {
    localStorage.clear()
    mockFetch.mockReset()
    configureApiClient(() => null, vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('prefixes requests with /api', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ ok: true }))
    await apiFetch('/users/me')
    expect(mockFetch).toHaveBeenCalledWith('/api/users/me', expect.any(Object))
  })

  it('injects Authorization header when token is present', async () => {
    configureApiClient(() => 'test-token', vi.fn())
    mockFetch.mockResolvedValueOnce(jsonResponse({ ok: true }))
    await apiFetch('/users/me')
    const headers: Headers = mockFetch.mock.calls[0][1].headers
    expect(headers.get('Authorization')).toBe('Bearer test-token')
  })

  it('retries with refreshed token on 401 then succeeds', async () => {
    configureApiClient(() => 'expired-token', vi.fn())
    localStorage.setItem('refresh_token', 'valid-refresh')

    // First call returns 401, refresh returns new token, retry succeeds
    mockFetch
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ access_token: 'new-token', refresh_token: 'r' }))
      .mockResolvedValueOnce(jsonResponse({ id: 1 }))

    const result = await apiFetch('/users/me')
    expect(result).toEqual({ id: 1 })
    expect(mockFetch).toHaveBeenCalledTimes(3)
  })

  it('calls onUnauthorized and throws when refresh fails', async () => {
    const onUnauthorized = vi.fn()
    configureApiClient(() => 'expired-token', onUnauthorized)
    localStorage.setItem('refresh_token', 'bad-refresh')

    mockFetch
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // refresh fails
      .mockResolvedValueOnce(new Response(null, { status: 401 })) // retry also 401

    await expect(apiFetch('/users/me')).rejects.toThrow('Unauthorized')
    expect(onUnauthorized).toHaveBeenCalled()
  })

  it('sends refresh token as query param, not body', async () => {
    configureApiClient(() => 'expired', vi.fn())
    localStorage.setItem('refresh_token', 'my-refresh-token')

    mockFetch
      .mockResolvedValueOnce(new Response(null, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ access_token: 'new', refresh_token: 'r' }))
      .mockResolvedValueOnce(jsonResponse({}))

    await apiFetch('/users/me')

    const refreshCall = mockFetch.mock.calls[1]
    const refreshUrl: string = refreshCall[0]
    expect(refreshUrl).toContain('refresh_token=my-refresh-token')
    expect(refreshCall[1].body).toBeUndefined()
  })

  it('throws ApiError with status on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ detail: 'Not found' }, 404))
    await expect(apiFetch('/missing')).rejects.toMatchObject({
      name: 'ApiError',
      status: 404,
      message: 'Not found',
    })
  })
})
