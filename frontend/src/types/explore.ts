export interface ExploreAlbumItem {
  id: number
  spotify_album_id: string | null
  title: string
  artist: string
  artist_url: string | null
  cover_url: string | null
  release_date: string | null
  avg_rating: number | null
  review_count: number
  nomination_count: number
  weighted_score: number | null
}

export interface ExploreAlbumsPage {
  items: ExploreAlbumItem[]
  next_offset: number | null
}

export interface ExploreAlbumsParams {
  offset?: number
  limit?: number
  min_reviews?: number | null
  sort_by?: string
  q?: string | null
}

export interface ExploreGroupsParams {
  offset?: number
  limit?: number
  q?: string | null
  group_type?: 'all' | 'human' | 'bot'
}

export interface ExploreGroupItem {
  id: number
  name: string
  is_public: boolean
  is_global: boolean
  member_count: number
  created_at: string
}

export interface ExploreGroupsPage {
  items: ExploreGroupItem[]
  next_offset: number | null
}

export interface ExploreUserItem {
  id: number
  username: string
  member_since: string
  review_count: number
  total_groups: number
}

export interface ExploreUsersParams {
  offset?: number
  limit?: number
  q?: string | null
}

export interface ExploreUsersPage {
  items: ExploreUserItem[]
  next_offset: number | null
}

export interface ArtistNominationItem {
  artist: string
  artist_url: string | null
  nomination_count: number
  unique_albums: number
}

export interface SiteStatsResponse {
  total_albums_nominated: number
  total_reviews: number
  total_active_groups: number
  total_active_members: number
  top_rated_albums: ExploreAlbumItem[]
  bottom_rated_albums: ExploreAlbumItem[]
  most_nominated_artists: ArtistNominationItem[]
  most_nominated_albums: ExploreAlbumItem[]
}
