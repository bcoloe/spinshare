import type { UnifiedTrack } from '../context/PlayerContext'

export async function fetchAppleMusicAlbumTracks(
  developerToken: string,
  albumId: string,
  storefront = 'us',
): Promise<UnifiedTrack[]> {
  const resp = await fetch(
    `https://api.music.apple.com/v1/catalog/${storefront}/albums/${albumId}/tracks`,
    { headers: { Authorization: `Bearer ${developerToken}` } },
  )
  if (!resp.ok) throw new Error(`Apple Music API error: ${resp.status}`)
  const data = await resp.json()
  return (data.data ?? []).map((song: {
    id: string
    attributes: { name: string; trackNumber: number; durationInMillis: number; artistName: string }
  }) => ({
    id: song.id,
    name: song.attributes.name,
    trackNumber: song.attributes.trackNumber,
    durationMs: song.attributes.durationInMillis,
    artist: song.attributes.artistName,
  }))
}

export interface AppleMusicPlaylist {
  id: string
  name: string
  imageUrl: string | null
}

export async function fetchAppleMusicUserPlaylists(
  developerToken: string,
  userToken: string,
): Promise<AppleMusicPlaylist[]> {
  const resp = await fetch('https://api.music.apple.com/v1/me/library/playlists?limit=100', {
    headers: {
      Authorization: `Bearer ${developerToken}`,
      'Music-User-Token': userToken,
    },
  })
  if (!resp.ok) throw new Error(`Apple Music API error: ${resp.status}`)
  const data = await resp.json()
  return (data.data ?? []).map((p: {
    id: string
    attributes: { name: string; artwork?: { url?: string } }
  }) => ({
    id: p.id,
    name: p.attributes.name,
    imageUrl: p.attributes.artwork?.url
      ? p.attributes.artwork.url.replace('{w}', '40').replace('{h}', '40')
      : null,
  }))
}

export async function addSongsToAppleMusicPlaylist(
  playlistId: string,
  songIds: string[],
  developerToken: string,
  userToken: string,
): Promise<void> {
  const resp = await fetch(
    `https://api.music.apple.com/v1/me/library/playlists/${playlistId}/tracks`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${developerToken}`,
        'Music-User-Token': userToken,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        data: songIds.map((id) => ({ id, type: 'songs' })),
      }),
    },
  )
  if (!resp.ok) throw new Error(`Apple Music API error: ${resp.status}`)
}
