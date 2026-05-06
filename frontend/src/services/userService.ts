import { apiFetch } from './apiClient'
import type {
  NominationDecadeBreakdownResponse,
  PublicProfileResponse,
  ReviewStatsResponse,
  UserGroupItem,
  UserResponse,
  UserReviewItem,
} from '../types/auth'

export const userService = {
  search(query: string): Promise<UserResponse[]> {
    return apiFetch(`/users/search/${encodeURIComponent(query)}`)
  },

  getProfile(username: string): Promise<PublicProfileResponse> {
    return apiFetch(`/users/${encodeURIComponent(username)}/profile`)
  },

  getReviews(username: string): Promise<UserReviewItem[]> {
    return apiFetch(`/users/${encodeURIComponent(username)}/reviews`)
  },

  getNominationBreakdown(username: string): Promise<NominationDecadeBreakdownResponse> {
    return apiFetch(`/users/${encodeURIComponent(username)}/nominations/breakdown`)
  },

  getReviewStats(username: string): Promise<ReviewStatsResponse> {
    return apiFetch(`/users/${encodeURIComponent(username)}/review-stats`)
  },

  getGroups(username: string): Promise<UserGroupItem[]> {
    return apiFetch(`/users/${encodeURIComponent(username)}/groups`)
  },
}
