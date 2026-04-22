// Client-side Spotify Web API calls using a user access token.
// Token is passed in rather than stored at module level so callers
// always supply a fresh one (obtained via getSpotifyToken()).

export interface SpotifyPlaylist {
  id: string
  name: string
  imageUrl: string | null
}

async function spotifyFetch(token: string, path: string, init?: RequestInit): Promise<Response> {
  // Only set Content-Type when we're actually sending a body — sending it
  // on bodyless PUTs/DELETEs causes Spotify to return 403 Forbidden.
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (init?.body) headers['Content-Type'] = 'application/json'

  const resp = await fetch(`https://api.spotify.com/v1${path}`, {
    ...init,
    headers: { ...headers, ...init?.headers },
  })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    const detail = body?.error?.message ?? resp.statusText
    if (resp.status === 403) {
      throw new Error(`Spotify permission denied (${detail}) — please reconnect your account in Settings.`)
    }
    throw new Error(`Spotify error ${resp.status}: ${detail}`)
  }
  return resp
}

export async function fetchUserPlaylists(token: string): Promise<SpotifyPlaylist[]> {
  // Fetch playlists and the current user's ID in parallel so we can filter
  // to only playlists the user owns — followed playlists return 403 on write.
  const [playlistsResp, meResp] = await Promise.all([
    spotifyFetch(token, '/me/playlists?limit=50'),
    spotifyFetch(token, '/me'),
  ])
  const myId = (await meResp.json()).id
  const data = await playlistsResp.json()
  return data.items
    .filter((p: { id: string | null; owner?: { id: string } }) => p?.id && p.owner?.id === myId)
    .map((p: { id: string; name: string; images: Array<{ url: string }> }) => ({
      id: p.id,
      name: p.name,
      imageUrl: p.images?.[0]?.url ?? null,
    }))
}

export async function addTracksToPlaylist(
  token: string,
  playlistId: string,
  uris: string[]
): Promise<void> {
  for (let i = 0; i < uris.length; i += 100) {
    await spotifyFetch(token, `/playlists/${playlistId}/items`, {
      method: 'POST',
      body: JSON.stringify({ uris: uris.slice(i, i + 100) }),
    })
  }
}

export async function removeTracksFromPlaylist(
  token: string,
  playlistId: string,
  uris: string[]
): Promise<void> {
  for (let i = 0; i < uris.length; i += 100) {
    await spotifyFetch(token, `/playlists/${playlistId}/items`, {
      method: 'DELETE',
      body: JSON.stringify({ items: uris.slice(i, i + 100).map((uri) => ({ uri })) }),
    })
  }
}

// Returns the set of playlist IDs (from the provided list) that contain at least
// one of the target URIs. Paginates through all pages using a minimal fields filter.
export async function getPlaylistsContainingUris(
  token: string,
  playlists: SpotifyPlaylist[],
  targetUris: string[]
): Promise<Set<string>> {
  if (targetUris.length === 0 || playlists.length === 0) return new Set()

  const targetSet = new Set(targetUris)

  const results = await Promise.all(
    playlists.map(async (pl) => {
      let path: string | null =
        `/playlists/${pl.id}/items?fields=items(item(uri)),next&limit=50`
      while (path) {
        const resp = await spotifyFetch(token, path)
        const data = await resp.json()
        for (const entry of data.items ?? []) {
          if (entry?.item?.uri && targetSet.has(entry.item.uri)) return pl.id
        }
        path = data.next ? data.next.replace('https://api.spotify.com/v1', '') : null
      }
      return null
    })
  )

  return new Set(results.filter((id): id is string => id !== null))
}

export async function isAlbumSaved(token: string, albumId: string): Promise<boolean> {
  const uri = `spotify:album:${albumId}`
  const resp = await spotifyFetch(token, `/me/library/contains?uris=${encodeURIComponent(uri)}`)
  const data = await resp.json()
  return data[0] === true
}

export async function saveAlbum(token: string, albumId: string): Promise<void> {
  await spotifyFetch(token, '/me/library', {
    method: 'PUT',
    body: JSON.stringify({ uris: [`spotify:album:${albumId}`] }),
  })
}

export async function unsaveAlbum(token: string, albumId: string): Promise<void> {
  await spotifyFetch(token, '/me/library', {
    method: 'DELETE',
    body: JSON.stringify({ uris: [`spotify:album:${albumId}`] }),
  })
}
