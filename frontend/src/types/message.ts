export interface MessageMention {
  user_id: number
  username: string
}

export interface MessageResponse {
  id: number
  group_id: number
  // null once the author deletes their account — rendered as "[deleted user]".
  user_id: number | null
  username: string | null
  // Empty string when is_deleted; the server never sends deleted content.
  body: string
  created_at: string
  edited_at: string | null
  is_deleted: boolean
  mentions: MessageMention[]
}

export interface PresenceMember {
  user_id: number
  username: string
}

/** Unread message count for one group. Only non-zero groups are returned. */
export interface GroupUnread {
  group_id: number
  count: number
}

export interface ChatTicketResponse {
  ticket: string
  expires_in: number
}

// ── Socket events (server → client) ──────────────────────────────────────────
// The socket is receive-only; nothing the client sends over it mutates state.

export interface PresenceSnapshotEvent {
  type: 'presence.snapshot'
  user_id: number
  // Keyed by group id as a string, since JSON object keys are always strings.
  groups: Record<string, PresenceMember[]>
}

export interface PresenceJoinEvent {
  type: 'presence.join'
  group_id: number
  user_id: number
  username: string
}

export interface PresenceLeaveEvent {
  type: 'presence.leave'
  group_id: number
  user_id: number
}

export interface MessageNewEvent {
  type: 'message.new'
  message: MessageResponse
}

export interface MessageDeletedEvent {
  type: 'message.deleted'
  message: MessageResponse
}

export type ChatSocketEvent =
  | PresenceSnapshotEvent
  | PresenceJoinEvent
  | PresenceLeaveEvent
  | MessageNewEvent
  | MessageDeletedEvent
