// Client-side Spotify Web API calls using a user access token.
// Token is passed in rather than stored at module level so callers
// always supply a fresh one (obtained via getSpotifyToken()).

export interface SpotifyPlaylist {
  id: string
  name: string
  imageUrl: string | null
  tracksTotal: number
}

async function spotifyFetch(token: string, path: string, init?: RequestInit): Promise<Response> {
  const resp = await fetch(`https://api.spotify.com/v1${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })
  if (resp.status === 403) {
    throw new Error('Missing Spotify permissions — please reconnect your account in Settings.')
  }
  return resp
}

export async function fetchUserPlaylists(token: string): Promise<SpotifyPlaylist[]> {
  const resp = await spotifyFetch(token, '/me/playlists?limit=50')
  if (!resp.ok) throw new Error('Could not load playlists — please reconnect your Spotify account.')
  const data = await resp.json()
  return data.items.map((p: { id: string; name: string; images: Array<{ url: string }>; tracks: { total: number } }) => ({
    id: p.id,
    name: p.name,
    imageUrl: p.images?.[0]?.url ?? null,
    tracksTotal: p.tracks.total,
  }))
}

export async function addTracksToPlaylist(
  token: string,
  playlistId: string,
  uris: string[]
): Promise<void> {
  // Spotify allows max 100 URIs per request; chunk if needed
  for (let i = 0; i < uris.length; i += 100) {
    await spotifyFetch(token, `/playlists/${playlistId}/tracks`, {
      method: 'POST',
      body: JSON.stringify({ uris: uris.slice(i, i + 100) }),
    })
  }
}

export async function isAlbumSaved(token: string, albumId: string): Promise<boolean> {
  const resp = await spotifyFetch(token, `/me/albums/contains?ids=${albumId}`)
  if (!resp.ok) return false
  const data = await resp.json()
  return data[0] === true
}

export async function saveAlbum(token: string, albumId: string): Promise<void> {
  await spotifyFetch(token, `/me/albums?ids=${albumId}`, { method: 'PUT' })
}

export async function unsaveAlbum(token: string, albumId: string): Promise<void> {
  await spotifyFetch(token, `/me/albums?ids=${albumId}`, { method: 'DELETE' })
}
