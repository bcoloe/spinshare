import { apiFetch } from './apiClient'
import type { RecapResponse, RecapSummary } from '../types/recap'

export const recapService = {
  listRecaps(groupId: number): Promise<RecapResponse[]> {
    return apiFetch(`/groups/${groupId}/recaps`)
  },

  getLatest(groupId: number): Promise<RecapResponse | null> {
    return apiFetch(`/groups/${groupId}/recaps/latest`)
  },

  getRecap(groupId: number, recapId: number): Promise<RecapResponse> {
    return apiFetch(`/groups/${groupId}/recaps/${recapId}`)
  },

  markSeen(groupId: number, recapId: number): Promise<void> {
    return apiFetch(`/groups/${groupId}/recaps/${recapId}/seen`, { method: 'POST' })
  },

  getPending(): Promise<RecapSummary[]> {
    return apiFetch('/users/me/recaps/pending')
  },
}
