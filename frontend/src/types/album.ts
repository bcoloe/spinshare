export interface AlbumResponse {
  id: number
  spotify_album_id: string
  title: string
  artist: string
  release_date: string | null
  cover_url: string | null
  youtube_music_id: string | null
  apple_music_album_id: string | null
  added_at: string
  genres: string[]
}

export interface GroupAlbumResponse {
  id: number
  group_id: number
  album_id: number
  added_by: number | null  // null for chaos-selected albums
  status: 'pending' | 'selected' | 'reviewed'
  added_at: string
  selected_date: string | null
  album: AlbumResponse
  nomination_count: number
  nominator_user_ids: number[]
  avg_rating: number | null
  review_count: number
}

export interface ReviewCreate {
  rating?: number
  comment?: string
  is_draft?: boolean
}

export interface ReviewUpdate {
  rating?: number
  comment?: string
  is_draft?: boolean
}

export interface ReviewResponse {
  id: number
  album_id: number
  user_id: number
  rating: number | null
  comment: string | null
  is_draft: boolean
  reviewed_at: string
  updated_at: string | null
}

export interface AlbumReviewItem {
  id: number
  album_id: number
  user_id: number
  username: string
  first_name: string | null
  last_name: string | null
  rating: number | null
  comment: string | null
  is_draft: boolean
  reviewed_at: string
  updated_at: string | null
}

export interface HistogramBucket {
  bucket_start: number
  bucket_end: number
  count: number
}

export interface AlbumStatsResponse {
  average_rating: number | null
  review_count: number
  histogram: HistogramBucket[]
}

export interface NominationGuessCreate {
  guessed_user_id: number | null  // null = chaos guess (outside the group)
}

export interface NominationGuessResponse {
  id: number
  group_album_id: number
  guessing_user_id: number
  guessed_user_id: number | null  // null for chaos guesses
  correct: boolean
  created_at: string
}

export interface UserNominationResponse {
  album: AlbumResponse
  nominated_group_ids: number[]
}

export interface CheckGuessResponse {
  guess: NominationGuessResponse
  correct: boolean
  nominator_user_ids: number[]
  nominator_usernames: string[]
  is_chaos_selection: boolean
}

export interface NominationCountResponse {
  pending_count: number
  today_count: number
}

export interface GuessOptionUser {
  user_id: number
  username: string
  first_name?: string | null
  last_name?: string | null
}

export interface GuessOptionsResponse {
  options: GuessOptionUser[]
  has_chaos_option: boolean
}
