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

export interface MemberGuessResult {
  guessing_user_id: number
  guessing_username: string
  guessed_user_id: number | null
  guessed_username: string | null
  is_chaos: boolean
  correct: boolean
}

export interface AlbumGuessStatsResponse {
  group_album_id: number
  nominator_user_id: number
  nominator_username: string
  total_guesses: number
  correct_guesses: number
  guesses: MemberGuessResult[]
}
