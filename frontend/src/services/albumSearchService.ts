import { apiFetch } from './apiClient'
import type { AlbumResponse, GroupAlbumResponse, UserNominationResponse } from '../types/album'

export interface AlbumSearchResult {
  spotify_album_id: string
  title: string
  artist: string
  release_date: string | null
  cover_url: string | null
  genres: string[]
}

export interface AlbumSearchParams {
  q?: string
  artist?: string
  album?: string
}

export const albumSearchService = {
  search(params: AlbumSearchParams): Promise<AlbumSearchResult[]> {
    const qs = new URLSearchParams()
    if (params.q) qs.set('q', params.q)
    if (params.artist) qs.set('artist', params.artist)
    if (params.album) qs.set('album', params.album)
    return apiFetch(`/albums/search?${qs.toString()}`)
  },

  getOrCreate(data: AlbumSearchResult): Promise<AlbumResponse> {
    return apiFetch('/albums/get-or-create', {
      method: 'POST',
      body: JSON.stringify({
        spotify_album_id: data.spotify_album_id,
        title: data.title,
        artist: data.artist,
        release_date: data.release_date,
        cover_url: data.cover_url,
        genres: data.genres,
      }),
    })
  },

  nominateToGroup(groupId: number, albumId: number): Promise<GroupAlbumResponse> {
    return apiFetch(`/groups/${groupId}/albums`, {
      method: 'POST',
      body: JSON.stringify({ album_id: albumId }),
    })
  },

  getGroupAlbums(groupId: number, status?: string): Promise<GroupAlbumResponse[]> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    return apiFetch(`/groups/${groupId}/albums${qs}`)
  },

  getMyNominations(): Promise<UserNominationResponse[]> {
    return apiFetch('/users/me/nominations')
  },

  removeGroupAlbum(groupId: number, groupAlbumId: number): Promise<void> {
    return apiFetch(`/groups/${groupId}/albums/${groupAlbumId}`, { method: 'DELETE' })
  },

  updateStatus(groupId: number, groupAlbumId: number, status: 'pending' | 'selected' | 'reviewed'): Promise<GroupAlbumResponse> {
    return apiFetch(`/groups/${groupId}/albums/${groupAlbumId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  },
}
