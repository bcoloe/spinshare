import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../hooks/useAuth'
import { messageService } from '../services/messageService'
import type {
  ChatSocketEvent,
  MessageResponse,
  PresenceMember,
} from '../types/message'
import { chatKeys } from '../hooks/chatKeys'

// The socket opens once per session at the app shell, not per chat panel, so
// presence dots work anywhere in the app without the chat drawer being open.
// One idle socket per logged-in user costs the server nothing — it holds no
// database connection and performs no queries while idle.

const WS_UNAUTHORIZED = 4001
const BASE_RETRY_MS = 1000
const MAX_RETRY_MS = 30_000

interface ChatSocketValue {
  isConnected: boolean
  /** Online members by group id. Empty until the snapshot arrives. */
  presenceByGroup: Record<number, PresenceMember[]>
  onlineUserIds: (groupId: number) => Set<number>
}

export const ChatSocketContext = createContext<ChatSocketValue | null>(null)

function socketUrl(ticket: string): string {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/api/ws/chat?ticket=${encodeURIComponent(ticket)}`
}

export function ChatSocketProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const [isConnected, setIsConnected] = useState(false)
  const [presenceByGroup, setPresenceByGroup] = useState<Record<number, PresenceMember[]>>({})

  const socketRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<number>(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Guards against a reconnect scheduled by an old socket resurrecting itself
  // after the user has logged out or the component has unmounted.
  const cancelledRef = useRef(false)

  const applyEvent = useCallback(
    (event: ChatSocketEvent) => {
      switch (event.type) {
        case 'presence.snapshot': {
          const next: Record<number, PresenceMember[]> = {}
          for (const [groupId, members] of Object.entries(event.groups)) {
            next[Number(groupId)] = members
          }
          setPresenceByGroup(next)
          break
        }
        case 'presence.join': {
          setPresenceByGroup((prev) => {
            const members = prev[event.group_id] ?? []
            if (members.some((m) => m.user_id === event.user_id)) return prev
            return {
              ...prev,
              [event.group_id]: [
                ...members,
                { user_id: event.user_id, username: event.username },
              ].sort((a, b) => a.user_id - b.user_id),
            }
          })
          break
        }
        case 'presence.leave': {
          setPresenceByGroup((prev) => {
            const members = prev[event.group_id]
            if (!members) return prev
            return {
              ...prev,
              [event.group_id]: members.filter((m) => m.user_id !== event.user_id),
            }
          })
          break
        }
        case 'message.new': {
          const message = event.message
          queryClient.setQueryData<MessageResponse[]>(
            chatKeys.messages(message.group_id),
            (existing) => {
              if (!existing) return existing
              // The author already has this message from their own POST
              // response — appending again would double it.
              if (existing.some((m) => m.id === message.id)) return existing
              return [...existing, message]
            },
          )
          break
        }
        case 'message.deleted': {
          const message = event.message
          queryClient.setQueryData<MessageResponse[]>(
            chatKeys.messages(message.group_id),
            (existing) =>
              existing?.map((m) => (m.id === message.id ? message : m)),
          )
          break
        }
      }
    },
    [queryClient],
  )

  // `connect` and `scheduleRetry` are mutually recursive: a failed connect
  // schedules a retry, and a retry calls connect. This ref breaks the cycle so
  // neither has to be declared before the other.
  const connectRef = useRef<() => void>(() => {})

  const scheduleRetry = useCallback(() => {
    if (cancelledRef.current) return
    if (retryTimerRef.current) return

    // Exponential backoff with jitter. The browser WebSocket API does not
    // reconnect on its own, and `systemctl restart` on every deploy drops every
    // socket at once — without jitter every client would stampede back together.
    const delay = Math.min(BASE_RETRY_MS * 2 ** retryRef.current, MAX_RETRY_MS)
    const jittered = delay * (0.5 + Math.random() * 0.5)
    retryRef.current += 1

    retryTimerRef.current = setTimeout(() => {
      retryTimerRef.current = null
      connectRef.current()
    }, jittered)
  }, [])

  const connect = useCallback(async () => {
    if (cancelledRef.current) return
    if (socketRef.current) return

    let ticket: string
    try {
      ticket = (await messageService.createTicket()).ticket
    } catch {
      // Could not mint a ticket (offline, server down). Back off and retry —
      // the app works without the socket, it just falls back to polling.
      scheduleRetry()
      return
    }
    if (cancelledRef.current) return

    const socket = new WebSocket(socketUrl(ticket))
    socketRef.current = socket

    socket.onopen = () => {
      retryRef.current = 0
      setIsConnected(true)
    }

    socket.onmessage = (raw) => {
      try {
        applyEvent(JSON.parse(raw.data) as ChatSocketEvent)
      } catch {
        // A frame we cannot parse is not worth tearing the connection down for.
      }
    }

    socket.onclose = (closeEvent) => {
      socketRef.current = null
      setIsConnected(false)
      setPresenceByGroup({})

      // 4001 means the ticket was rejected. Retrying immediately with a fresh
      // ticket would just spin, so fall through to the same backoff — but the
      // distinct code keeps the reason visible in logs.
      if (closeEvent.code === WS_UNAUTHORIZED) {
        console.warn('Chat socket rejected the ticket; will retry with a new one')
      }
      scheduleRetry()
    }

    socket.onerror = () => {
      // onclose always follows, which is where reconnection is handled.
      socket.close()
    }
  }, [applyEvent, scheduleRetry])

  useEffect(() => {
    connectRef.current = () => void connect()
  }, [connect])

  useEffect(() => {
    if (!user) return

    cancelledRef.current = false
    void connect()

    return () => {
      cancelledRef.current = true
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }
      // Clear onclose first so teardown does not schedule a reconnect.
      const socket = socketRef.current
      if (socket) {
        socket.onclose = null
        socket.close()
        socketRef.current = null
      }
      setIsConnected(false)
      setPresenceByGroup({})
    }
  }, [user, connect])

  // A socket that dropped while the tab was backgrounded should come back as
  // soon as the user returns, rather than waiting out the remaining backoff.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState !== 'visible') return
      if (socketRef.current || !user) return
      retryRef.current = 0
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current)
        retryTimerRef.current = null
      }
      void connect()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => document.removeEventListener('visibilitychange', onVisible)
  }, [user, connect])

  const onlineUserIds = useCallback(
    (groupId: number) => new Set((presenceByGroup[groupId] ?? []).map((m) => m.user_id)),
    [presenceByGroup],
  )

  const value = useMemo(
    () => ({ isConnected, presenceByGroup, onlineUserIds }),
    [isConnected, presenceByGroup, onlineUserIds],
  )

  return <ChatSocketContext.Provider value={value}>{children}</ChatSocketContext.Provider>
}
