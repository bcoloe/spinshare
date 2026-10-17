import type { QueryClient } from '@tanstack/react-query'
import type { MessageReactions, MessageResponse } from '../types/message'
import { chatKeys } from './chatKeys'

/**
 * Write a message's reaction aggregate into the chat cache.
 *
 * Shared by the reaction mutation and the socket handler, which race: a
 * mutation's response and another member's broadcast can arrive in either
 * order. The version decides — an aggregate older than the one held is
 * dropped. Only the reactions are replaced, never the whole message, so a
 * reaction update can't roll back an edit either.
 */
export function applyReactions(qc: QueryClient, update: MessageReactions) {
  qc.setQueryData<MessageResponse[]>(chatKeys.messages(update.group_id), (existing) =>
    existing?.map((m) =>
      m.id === update.message_id && !m.is_deleted && update.version > m.reactions_version
        ? { ...m, reactions: update.reactions, reactions_version: update.version }
        : m,
    ),
  )
}

/**
 * Apply a whole message (an edit) without letting it roll reactions back: they
 * travel on their own versioned event, so keep whichever copy is newer.
 */
export function withNewerReactions(next: MessageResponse, held: MessageResponse): MessageResponse {
  return held.reactions_version > next.reactions_version
    ? { ...next, reactions: held.reactions, reactions_version: held.reactions_version }
    : next
}
