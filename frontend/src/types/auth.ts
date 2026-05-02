export interface UserResponse {
  id: number
  email: string
  username: string
  created_at: string
}

export interface UserWithStats extends UserResponse {
  total_groups: number
  created_groups: number
  total_reviews: number
  albums_added: number
  has_spotify: boolean
}

export interface LoginRequest {
  email?: string
  username?: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserResponse
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
}

export interface UserUpdate {
  email?: string
  username?: string
  password?: string
}

export interface PublicProfileResponse {
  username: string
  member_since: string
  total_reviews: number
  total_groups: number
  albums_nominated: number
}

export interface UserReviewItem {
  review_id: number
  album_id: number
  title: string
  artist: string
  cover_url: string | null
  release_date: string | null
  genres: string[]
  rating: number
  comment: string | null
  reviewed_at: string
}

export interface DecadeBreakdownItem {
  decade: string
  count: number
}

export interface NominationDecadeBreakdownResponse {
  total_nominations: number
  decade_breakdown: DecadeBreakdownItem[]
}
