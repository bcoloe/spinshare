import { apiFetch } from './apiClient'
import type { UserResponse } from '../types/auth'

export const userService = {
  search(query: string): Promise<UserResponse[]> {
    return apiFetch(`/users/search/${encodeURIComponent(query)}`)
  },
}
