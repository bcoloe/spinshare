import { useContext, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChatSocketContext } from '../context/ChatSocketContext'
import { messageService } from '../services/messageService'
import type { MessageResponse } from '../types/message'
import { chatKeys } from './chatKeys'

export { chatKeys }

/**
 * How much scrollback a chat loads at a time.
 *
 * Opening a chat fetches the most recent page, not the room's whole history —
 * an old group could hold thousands of messages nobody scrolled to. Older pages
 * load on demand as the reader scrolls up.
 *
 * Sent explicitly on every request rather than relying on the server default,
 * so the page size the client pages by and the page size it receives cannot
 * drift apart.
 */
export const CHAT_PAGE_SIZE = 30

// Matches MAX_HISTORY_LIMIT on the server. Only the catch-up delta asks for
// this much — see the gap handling in useChatMessages.
const DELTA_LIMIT = 100

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
      // re-downloading the whole window. `after` is the last id we hold.
      if (existing?.length) {
        const delta = await messageService.getMessages(groupId, {
          after: existing[existing.length - 1].id,
          limit: DELTA_LIMIT,
        })

        // A full page of delta means more was missed than one request can
        // carry, and the server returns the *newest* matches — so stitching it
        // onto what we hold would leave a silent hole in the middle. Start over
        // from the latest page instead; the missing stretch is reachable by
        // scrolling back, which is honest about what we have.
        if (delta.length >= DELTA_LIMIT) {
          return messageService.getMessages(groupId, { limit: CHAT_PAGE_SIZE })
        }

        return delta.length ? dedupe([...existing, ...delta]) : existing
      }

      return messageService.getMessages(groupId, { limit: CHAT_PAGE_SIZE })
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

/**
 * Backwards paging for the chat scrollback.
 *
 * Prepends into the same flat cache the socket and the poll append to, so there
 * is still exactly one array of messages per group and every writer keeps its
 * simple append/patch shape.
 *
 * `hasOlder` starts null — meaning "not known yet". Callers should fall back to
 * a length check until a page has actually come back; the first fetch that
 * returns a short page settles it for good.
 */
export function useLoadOlderMessages(groupId: number) {
  const qc = useQueryClient()
  const [hasOlder, setHasOlder] = useState<boolean | null>(null)

  // Switching groups invalidates everything we learned about the last one.
  useEffect(() => setHasOlder(null), [groupId])

  const mutation = useMutation({
    mutationFn: async () => {
      const existing = qc.getQueryData<MessageResponse[]>(chatKeys.messages(groupId))
      if (!existing?.length) return []
      return messageService.getMessages(groupId, {
        before: existing[0].id,
        limit: CHAT_PAGE_SIZE,
      })
    },
    onSuccess: (older) => {
      // A short page means we reached the start of the conversation.
      setHasOlder(older.length >= CHAT_PAGE_SIZE)
      if (!older.length) return
      qc.setQueryData<MessageResponse[]>(chatKeys.messages(groupId), (existing) =>
        dedupe([...older, ...(existing ?? [])]),
      )
    },
  })

  return {
    loadOlder: mutation.mutate,
    isLoadingOlder: mutation.isPending,
    hasOlder,
  }
}

/**
 * Retire this group's unread @mention notifications.
 *
 * Called while the chat is actually on screen: once the user is looking at the
 * conversation, a notification pointing them at it has nothing left to tell
 * them, and leaving it in the bell just means dismissing something they have
 * already read.
 */
export function useMarkChatSeen(groupId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => messageService.markChatSeen(groupId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notifications'] }),
  })
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
