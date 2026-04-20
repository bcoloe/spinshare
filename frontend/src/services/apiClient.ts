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

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null

  const res = await fetch(`/api/users/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
    method: 'POST',
  })
  if (!res.ok) return null

  const data = await res.json()
  return data.access_token ?? null
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
    const newToken = await refreshAccessToken()
    if (newToken) {
      // Notify context of the new token via a custom event
      window.dispatchEvent(new CustomEvent('token:refreshed', { detail: newToken }))
      headers.set('Authorization', `Bearer ${newToken}`)
      res = await fetch(`/api${path}`, { ...options, headers })
    }
  }

  if (res.status === 401) {
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
