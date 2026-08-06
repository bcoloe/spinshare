export interface LeaderboardEntry {
  username: string
  count: number
}

export interface RecapAlbumCard {
  album_id: number
  spotify_album_id: string | null
  title: string
  artist: string | null
  cover_url: string | null
  avg_rating: number
  review_count: number
  weighted_score: number
}

export interface MemberGuessAccuracy {
  username: string
  total: number
  correct: number
  pct: number
}

export interface GuessAccuracy {
  total_guesses: number
  correct_guesses: number
  pct: number
  per_member: MemberGuessAccuracy[]
}

export interface RecapData {
  albums_added: LeaderboardEntry[]
  albums_reviewed: LeaderboardEntry[]
  favorite_album: RecapAlbumCard | null
  least_favorite_album: RecapAlbumCard | null
  guess_accuracy: GuessAccuracy
}

export interface RecapResponse {
  id: number
  group_id: number
  week_start: string
  week_end: string
  generated_at: string
  data: RecapData
  seen: boolean
}

export interface RecapSummary {
  id: number
  group_id: number
  group_name: string
  week_start: string
  week_end: string
}
