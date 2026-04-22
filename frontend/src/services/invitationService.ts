import { apiFetch } from './apiClient'
import type { InvitationResponse } from '../types/group'

export const invitationService = {
  send(groupId: number, email: string): Promise<InvitationResponse> {
    return apiFetch(`/groups/${groupId}/invitations`, {
      method: 'POST',
      body: JSON.stringify({ email }),
    })
  },

  list(groupId: number): Promise<InvitationResponse[]> {
    return apiFetch(`/groups/${groupId}/invitations`)
  },

  revoke(groupId: number, invitationId: number): Promise<void> {
    return apiFetch(`/groups/${groupId}/invitations/${invitationId}`, { method: 'DELETE' })
  },

  getByToken(token: string): Promise<InvitationResponse> {
    return apiFetch(`/invitations/${token}`)
  },

  accept(token: string): Promise<InvitationResponse> {
    return apiFetch(`/invitations/${token}/accept`, { method: 'POST' })
  },

  decline(token: string): Promise<void> {
    return apiFetch(`/invitations/${token}/decline`, { method: 'POST' })
  },

  getMyPending(): Promise<InvitationResponse[]> {
    return apiFetch('/invitations/pending')
  },
}
