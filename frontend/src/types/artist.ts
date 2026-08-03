import type { AlbumResponse } from './album'

export interface ArtistAlbumItem {
  album: AlbumResponse
  nomination_count: number
  review_count: number
  average_rating: number | null
  rating_stddev: number | null
}

export interface ArtistOverviewResponse {
  artist: string
  album_count: number
  total_nominations: number
  total_reviews: number
  average_rating: number | null
  rating_stddev: number | null
  albums: ArtistAlbumItem[]
}
