import { apiFetch } from './apiClient'

export async function getSpotifyConnectUrl(): Promise<string> {
  const data = await apiFetch<{ url: string }>('/users/spotify/connect-url')
  return data.url
}

export async function disconnectSpotify(): Promise<void> {
  await apiFetch('/users/spotify', { method: 'DELETE' })
}
