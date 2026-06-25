type TokenGetter = () => string | null
type UnauthorizedHandler = () => void

let getToken: TokenGetter = () => null
let onUnauthorized: UnauthorizedHandler = () => {}

export function configureApiClient(
  tokenGetter: TokenGetter,
  unauthorizedHandler: UnauthorizedHandler,
) {
  getToken = tokenGetter
  onUnauthorized = unauthorizedHandler
}

// Thrown when the refresh endpoint returns 401 — the token is genuinely invalid.
// Distinct from transient server/network failures, which return null instead.
export class RefreshAuthError extends Error {
  constructor() {
    super('Refresh token rejected')
    this.name = 'RefreshAuthError'
  }
}

// Shared promise so concurrent 401s share one refresh call instead of racing.
// Also used by AuthContext startup so both paths deduplicate against each other.
let refreshPromise: Promise<string | null> | null = null

export async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise

  refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token')
      if (!refreshToken) return null

      const res = await fetch(`/api/users/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
        method: 'POST',
      })
      if (res.status === 401) throw new RefreshAuthError()
      if (!res.ok) return null

      const data = await res.json()
      if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token)
      return data.access_token ?? null
    } finally {
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers)

  const token = getToken()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }

  let res = await fetch(`/api${path}`, { ...options, headers })

  if (res.status === 401) {
    let newToken: string | null = null
    try {
      newToken = await refreshAccessToken()
    } catch (err) {
      if (err instanceof RefreshAuthError) {
        onUnauthorized()
        throw new Error('Unauthorized')
      }
      throw err
    }

    if (newToken) {
      // Notify context of the new token via a custom event
      window.dispatchEvent(new CustomEvent('token:refreshed', { detail: newToken }))
      headers.set('Authorization', `Bearer ${newToken}`)
      res = await fetch(`/api${path}`, { ...options, headers })
    } else {
      // Transient failure (DB down, network error): fail this request without
      // logging the user out so they can retry once the service recovers.
      const body = await res.json().catch(() => ({ detail: res.statusText }))
      throw new ApiError(res.status, body.detail ?? res.statusText, body)
    }
  }

  if (res.status === 401) {
    // Refresh succeeded but the freshly-issued token was immediately rejected —
    // something is genuinely wrong with the session.
    onUnauthorized()
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText, body)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
