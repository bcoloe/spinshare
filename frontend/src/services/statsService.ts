import { apiFetch } from './apiClient'
import type { AlbumGuessStatsResponse, AlbumReviewStatsResponse, UserGuessStatsResponse, UserWithStats } from '../types/stats'

export const statsService = {
  getMyStats(): Promise<UserWithStats> {
    return apiFetch('/users/me/stats')
  },

  getMyGuessStats(groupId: number, userId: number): Promise<UserGuessStatsResponse> {
    return apiFetch(`/stats/groups/${groupId}/members/${userId}/guesses`)
  },

  getAlbumReviewStats(albumId: number): Promise<AlbumReviewStatsResponse> {
    return apiFetch(`/stats/albums/${albumId}/reviews`)
  },

  getAlbumGuessStats(groupId: number, groupAlbumId: number): Promise<AlbumGuessStatsResponse> {
    return apiFetch(`/stats/groups/${groupId}/albums/${groupAlbumId}/guesses`)
  },
}
