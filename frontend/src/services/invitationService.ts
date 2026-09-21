import { apiFetch } from './apiClient'
import type { InvitationCreate, InvitationResponse } from '../types/group'

export const invitationService = {
  /** Invite by email address, or by username for a user surfaced by search. */
  send(groupId: number, invitee: InvitationCreate): Promise<InvitationResponse> {
    return apiFetch(`/groups/${groupId}/invitations`, {
      method: 'POST',
      body: JSON.stringify(invitee),
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
