import type { QueryClient } from '@tanstack/react-query'
import type { MessageReactions, MessageResponse } from '../types/message'
import { chatKeys } from './chatKeys'

/**
 * Write a message's reaction aggregate into the chat cache.
 *
 * Shared by the reaction mutation and the socket handler. Only the reactions
 * field is replaced — never the whole message — so a reaction update arriving
 * after an edit cannot roll the body back.
 */
export function applyReactions(qc: QueryClient, update: MessageReactions) {
  qc.setQueryData<MessageResponse[]>(chatKeys.messages(update.group_id), (existing) =>
    existing?.map((m) =>
      m.id === update.message_id && !m.is_deleted ? { ...m, reactions: update.reactions } : m,
    ),
  )
}
