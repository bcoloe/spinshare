export interface AlbumResponse {
  id: number
  spotify_album_id: string
  title: string
  artist: string
  release_date: string | null
  cover_url: string | null
  added_at: string
  genres: string[]
}

export interface GroupAlbumResponse {
  id: number
  group_id: number
  album_id: number
  added_by: number
  status: 'pending' | 'selected' | 'reviewed'
  added_at: string
  selected_date: string | null
  album: AlbumResponse
  nomination_count: number
  nominator_user_ids: number[]
}

export interface ReviewCreate {
  rating: number
  comment?: string
}

export interface ReviewResponse {
  id: number
  album_id: number
  user_id: number
  rating: number
  comment: string | null
  reviewed_at: string
  updated_at: string | null
}

export interface NominationGuessCreate {
  guessed_user_id: number
}

export interface NominationGuessResponse {
  id: number
  group_album_id: number
  guessing_user_id: number
  guessed_user_id: number
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
}
