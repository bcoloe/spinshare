import { apiFetch } from './apiClient'
import type {
  NominationDecadeBreakdownResponse,
  PublicProfileResponse,
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
}
