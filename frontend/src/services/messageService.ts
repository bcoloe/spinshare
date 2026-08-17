import { apiFetch } from './apiClient'
import type {
  ChatTicketResponse,
  GroupUnread,
  MessageResponse,
  PresenceMember,
} from '../types/message'

export const messageService = {
  /** Chat history, oldest-first. `before` pages backwards; `after` fetches the delta. */
  getMessages(
    groupId: number,
    params: { before?: number; after?: number; limit?: number } = {},
  ): Promise<MessageResponse[]> {
    const query = new URLSearchParams()
    if (params.before !== undefined) query.set('before', String(params.before))
    if (params.after !== undefined) query.set('after', String(params.after))
    if (params.limit !== undefined) query.set('limit', String(params.limit))
    const qs = query.toString()
    return apiFetch(`/groups/${groupId}/messages${qs ? `?${qs}` : ''}`)
  },

  postMessage(groupId: number, body: string): Promise<MessageResponse> {
    return apiFetch(`/groups/${groupId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    })
  },

  deleteMessage(messageId: number): Promise<MessageResponse> {
    return apiFetch(`/messages/${messageId}`, { method: 'DELETE' })
  },

  /**
   * Tell the server this group's chat is on screen: advances the read marker to
   * `lastMessageId` and retires the group's unread @mention notifications.
   * Idempotent — clearing nothing is a normal outcome.
   */
  markChatSeen(groupId: number, lastMessageId?: number): Promise<void> {
    return apiFetch(`/groups/${groupId}/chat/seen`, {
      method: 'POST',
      body: JSON.stringify({ last_message_id: lastMessageId ?? null }),
    })
  },

  /**
   * Unread message counts keyed by group id, for every group the user is in.
   *
   * Groups with nothing unread are absent rather than zero, so the map only
   * carries what there is to show.
   */
  async getUnreadCounts(): Promise<Record<number, number>> {
    const rows: GroupUnread[] = await apiFetch('/chat/unread')
    return Object.fromEntries(rows.map((r) => [r.group_id, r.count]))
  },

  /** Fallback for clients that could not open a socket — normally unused. */
  getPresence(groupId: number): Promise<PresenceMember[]> {
    return apiFetch(`/groups/${groupId}/presence`)
  },

  /**
   * Exchange the current session for a 30-second socket ticket.
   * The browser WebSocket API cannot set an Authorization header, so this is
   * how the socket authenticates without putting the access token in a URL.
   */
  createTicket(): Promise<ChatTicketResponse> {
    return apiFetch('/chat/ticket', { method: 'POST' })
  },
}
