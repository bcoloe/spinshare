import { apiFetch } from './apiClient'

export async function getSpotifyConnectUrl(): Promise<string> {
  const data = await apiFetch<{ url: string }>('/users/spotify/connect-url')
  return data.url
}

export async function getSpotifyToken(): Promise<string> {
  const data = await apiFetch<{ access_token: string }>('/users/spotify/token')
  return data.access_token
}

export async function disconnectSpotify(): Promise<void> {
  await apiFetch('/users/spotify', { method: 'DELETE' })
}

export async function getAppleMusicDeveloperToken(): Promise<string> {
  const data = await apiFetch<{ developer_token: string }>('/users/apple-music/developer-token')
  return data.developer_token
}
