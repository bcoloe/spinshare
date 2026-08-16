import { useContext } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChatSocketContext } from '../context/ChatSocketContext'
import { messageService } from '../services/messageService'
import type { MessageResponse } from '../types/message'
import { chatKeys } from './chatKeys'

export { chatKeys }

// While the socket is up, new messages arrive by push and no polling is needed
// at all. This interval is the fallback for clients that could not open a
// socket (a proxy that strips upgrades, a captive network). It is scoped to an
// open, visible chat panel so it can never run in the background — which is
// what keeps the database asleep when nobody is actively chatting.
const FALLBACK_POLL_MS = 5000

export function useChatSocket() {
  const ctx = useContext(ChatSocketContext)
  if (!ctx) throw new Error('useChatSocket must be used within ChatSocketProvider')
  return ctx
}

/** Online members of a group, straight from the socket's presence state. */
export function useGroupPresence(groupId: number) {
  const { presenceByGroup, onlineUserIds, isConnected } = useChatSocket()
  return {
    online: presenceByGroup[groupId] ?? [],
    onlineIds: onlineUserIds(groupId),
    isConnected,
  }
}

/**
 * Chat history for a group.
 *
 * `enabled` should track whether the chat panel is actually open — this query
 * is the only thing in the feature that touches the database on a timer, and
 * only when the socket is unavailable.
 */
export function useChatMessages(groupId: number, enabled: boolean) {
  const { isConnected } = useChatSocket()
  const qc = useQueryClient()

  return useQuery({
    queryKey: chatKeys.messages(groupId),
    queryFn: async () => {
      const existing = qc.getQueryData<MessageResponse[]>(chatKeys.messages(groupId))

      // On a reconnect or a refocus, fetch only what was missed rather than
      // re-downloading the whole window. `after` is the last id we hold, so a
      // gap of any length is closed in one request.
      if (existing?.length) {
        const delta = await messageService.getMessages(groupId, {
          after: existing[existing.length - 1].id,
        })
        return delta.length ? dedupe([...existing, ...delta]) : existing
      }

      return messageService.getMessages(groupId)
    },
    enabled: enabled && !!groupId,
    // Push keeps the cache fresh when connected; poll only as a fallback.
    refetchInterval: enabled && !isConnected ? FALLBACK_POLL_MS : false,
    refetchOnWindowFocus: enabled,
    staleTime: 0,
  })
}

/** Merge by id, newest state winning, and return in chronological order. */
function dedupe(messages: MessageResponse[]): MessageResponse[] {
  const byId = new Map<number, MessageResponse>()
  for (const message of messages) byId.set(message.id, message)
  return [...byId.values()].sort((a, b) => a.id - b.id)
}

export function useSendMessage(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: string) => messageService.postMessage(groupId, body),
    onSuccess: (message) => {
      // Append immediately rather than waiting for the socket to echo it back,
      // so the sender never sees their own message lag.
      qc.setQueryData<MessageResponse[]>(chatKeys.messages(groupId), (existing) => {
        if (!existing) return [message]
        if (existing.some((m) => m.id === message.id)) return existing
        return [...existing, message]
      })
    },
  })
}

export function useDeleteMessage(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (messageId: number) => messageService.deleteMessage(messageId),
    onSuccess: (message) => {
      qc.setQueryData<MessageResponse[]>(chatKeys.messages(groupId), (existing) =>
        existing?.map((m) => (m.id === message.id ? message : m)),
      )
    },
  })
}
