import { apiFetch } from './apiClient'
import type { GroupAlbumResponse } from '../types/album'

export interface PublicSpinResponse {
  draw_date: string
  albums: GroupAlbumResponse[]
}

export const publicService = {
  getTodaysSpin(): Promise<PublicSpinResponse> {
    return apiFetch('/public/spin')
  },
}
