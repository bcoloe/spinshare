export interface UserResponse {
  id: number
  email: string
  username: string
  first_name?: string | null
  last_name?: string | null
  name_is_public: boolean
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
  first_name?: string
  last_name?: string
}

export interface UserUpdate {
  email?: string
  username?: string
  first_name?: string | null
  last_name?: string | null
  name_is_public?: boolean
  password?: string
}

export interface PublicProfileResponse {
  username: string
  first_name?: string | null
  last_name?: string | null
  email: string
  member_since: string
  total_reviews: number
  total_groups: number
  albums_nominated: number
}

export interface RatingHistogramBucket {
  bucket: number
  count: number
}

export interface AvgRatingByDecadeItem {
  decade: string
  avg_rating: number
}

export interface GuessAccuracyStats {
  total: number
  correct: number
  pct: number | null
}

export interface UserGroupItem {
  id: number
  name: string
  member_count: number
  current_user_role: 'owner' | 'admin' | 'member' | null
}

export interface ReviewStatsResponse {
  average_rating: number | null
  rating_histogram: RatingHistogramBucket[]
  avg_rating_by_decade: AvgRatingByDecadeItem[]
  guess_accuracy: GuessAccuracyStats
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
