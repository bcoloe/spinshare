import { apiFetch } from './apiClient'
import type { ArtistOverviewResponse } from '../types/artist'

export const artistService = {
  getArtistOverview(name: string): Promise<ArtistOverviewResponse> {
    return apiFetch(`/artists/overview?name=${encodeURIComponent(name)}`)
  },
}
