export interface UserWithStats {
  id: number
  email: string
  username: string
  created_at: string
  total_groups: number
  created_groups: number
  total_reviews: number
  albums_added: number
  has_spotify: boolean
}

export interface UserGuessStatsResponse {
  user_id: number
  group_id: number
  total_guesses: number
  correct_guesses: number
  accuracy: number
}

export interface AlbumReviewStatsResponse {
  album_id: number
  review_count: number
  avg_rating: number | null
  min_rating: number | null
  max_rating: number | null
}
