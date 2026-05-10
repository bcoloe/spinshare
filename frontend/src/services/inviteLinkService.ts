import { apiFetch } from './apiClient'
import type { InviteLinkResponse } from '../types/group'

export const inviteLinkService = {
  get(groupId: number): Promise<InviteLinkResponse | null> {
    return apiFetch(`/groups/${groupId}/invite-link`)
  },

  createOrRotate(groupId: number): Promise<InviteLinkResponse> {
    return apiFetch(`/groups/${groupId}/invite-link`, { method: 'POST' })
  },

  revoke(groupId: number): Promise<void> {
    return apiFetch(`/groups/${groupId}/invite-link`, { method: 'DELETE' })
  },

  getByToken(token: string): Promise<InviteLinkResponse> {
    return apiFetch(`/join/${token}`)
  },

  accept(token: string): Promise<InviteLinkResponse> {
    return apiFetch(`/join/${token}/accept`, { method: 'POST' })
  },
}
