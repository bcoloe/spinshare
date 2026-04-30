import { apiFetch } from './apiClient'
import type {
  CheckGuessResponse,
  GroupAlbumResponse,
  NominationCountResponse,
  NominationGuessCreate,
  ReviewCreate,
  ReviewResponse,
} from '../types/album'

export const albumService = {
  getTodaysAlbums(groupId: number): Promise<GroupAlbumResponse[]> {
    return apiFetch(`/groups/${groupId}/albums/today`)
  },

  triggerDailySelection(groupId: number): Promise<GroupAlbumResponse[]> {
    return apiFetch(`/groups/${groupId}/albums/select-today`, { method: 'POST' })
  },

  getMyReview(albumId: number): Promise<ReviewResponse | null> {
    return apiFetch<ReviewResponse>(`/albums/${albumId}/reviews/me`).catch((err) => {
      if (err?.status === 404) return null
      throw err
    })
  },

  getAllReviews(albumId: number): Promise<ReviewResponse[]> {
    return apiFetch(`/albums/${albumId}/reviews`)
  },

  submitReview(albumId: number, data: ReviewCreate): Promise<ReviewResponse> {
    return apiFetch(`/albums/${albumId}/reviews`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  updateReview(albumId: number, reviewId: number, data: Partial<ReviewCreate>): Promise<ReviewResponse> {
    return apiFetch(`/albums/${albumId}/reviews/${reviewId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  getMyGuess(groupId: number, groupAlbumId: number): Promise<CheckGuessResponse | null> {
    return apiFetch<CheckGuessResponse>(
      `/groups/${groupId}/albums/${groupAlbumId}/guess/me`,
    ).catch((err) => {
      if (err?.status === 404) return null
      throw err
    })
  },

  checkGuess(
    groupId: number,
    groupAlbumId: number,
    data: NominationGuessCreate,
  ): Promise<CheckGuessResponse> {
    return apiFetch(`/groups/${groupId}/albums/${groupAlbumId}/check-guess`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  getNominationCount(groupId: number): Promise<NominationCountResponse> {
    return apiFetch(`/groups/${groupId}/nominations/count`)
  },
}
