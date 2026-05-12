import { apiFetch } from './apiClient'
import type {
  AlbumResponse,
  AlbumReviewItem,
  AlbumStatsResponse,
  CheckGuessResponse,
  GroupAlbumResponse,
  GuessOptionsResponse,
  NominationCountResponse,
  NominationGuessCreate,
  ReviewCreate,
  ReviewResponse,
  ReviewUpdate,
} from '../types/album'

export const albumService = {
  getTodaysAlbums(groupId: number): Promise<GroupAlbumResponse[]> {
    return apiFetch(`/groups/${groupId}/albums/today`)
  },

  triggerDailySelection(groupId: number, forceChaos = false): Promise<GroupAlbumResponse[]> {
    const url = forceChaos
      ? `/groups/${groupId}/albums/select-today?force_chaos=true`
      : `/groups/${groupId}/albums/select-today`
    return apiFetch(url, { method: 'POST' })
  },

  getMyReview(albumId: number): Promise<ReviewResponse | null> {
    return apiFetch<ReviewResponse>(`/albums/${albumId}/reviews/me`).catch((err) => {
      if (err?.status === 404) return null
      throw err
    })
  },

  getAlbumById(albumId: number): Promise<AlbumResponse> {
    return apiFetch(`/albums/${albumId}`)
  },

  getAllReviews(albumId: number, groupId?: number): Promise<AlbumReviewItem[]> {
    const url = groupId != null
      ? `/albums/${albumId}/reviews?group_id=${groupId}`
      : `/albums/${albumId}/reviews`
    return apiFetch(url)
  },

  getAlbumStats(albumId: number): Promise<AlbumStatsResponse> {
    return apiFetch(`/albums/${albumId}/stats`)
  },

  submitReview(albumId: number, data: ReviewCreate): Promise<ReviewResponse> {
    return apiFetch(`/albums/${albumId}/reviews`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  updateReview(albumId: number, reviewId: number, data: ReviewUpdate): Promise<ReviewResponse> {
    return apiFetch(`/albums/${albumId}/reviews/${reviewId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  getMyGuessesForGroup(groupId: number): Promise<CheckGuessResponse[]> {
    return apiFetch(`/groups/${groupId}/guesses/me`)
  },

  getMyReviewsForGroup(groupId: number): Promise<ReviewResponse[]> {
    return apiFetch(`/groups/${groupId}/reviews/me`)
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

  getGuessOptions(groupId: number, groupAlbumId: number): Promise<GuessOptionsResponse> {
    return apiFetch(`/groups/${groupId}/albums/${groupAlbumId}/guess/options`)
  },
}
