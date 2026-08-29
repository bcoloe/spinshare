import { createContext, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
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
// How long a connection must survive before its backoff counter is forgiven.
//
// Resetting the counter the instant `onopen` fires looks right and is not: a
// socket that opens and dies seconds later is *still failing*, but its backoff
// never grows, so it reconnects at full speed indefinitely. Each attempt costs
// a ticket mint and an identity lookup, which is enough to keep a serverless
// database from ever suspending. Requiring the connection to last first means a
// genuinely healthy socket resets as before, while a flapping one backs off.
const STABLE_AFTER_MS = 30_000

interface ChatSocketValue {
  isConnected: boolean
  /** Online members by group id. Empty until the snapshot arrives. */
  presenceByGroup: Record<number, PresenceMember[]>
  onlineUserIds: (groupId: number) => Set<number>
  /** Unread message counts by group id. Groups with nothing unread are absent. */
  unreadByGroup: Record<number, number>
  /**
   * Declare which group's chat is currently on screen, or null for none.
   *
   * Messages arriving for that group are not counted as unread — the user is
   * watching them land. Also zeroes whatever had accumulated, since opening the
   * conversation is what "reading it" means.
   */
  setActiveGroup: (groupId: number | null) => void
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

  // Unread counts live in the query cache rather than component state so the
  // seeded fetch and the socket's live increments write to one place — two
  // sources would drift the moment a message landed mid-fetch.
  const { data: unreadByGroup = {} } = useQuery({
    queryKey: chatKeys.unread(),
    queryFn: () => messageService.getUnreadCounts(),
    enabled: !!user,
  })

  // Read inside the socket handler, which closes over its own render's props.
  const activeGroupRef = useRef<number | null>(null)
  // Highest message id already counted toward the unread badge, per group.
  const countedThroughRef = useRef<Record<number, number>>({})
  const userIdRef = useRef<number | undefined>(user?.id)
  userIdRef.current = user?.id

  const setActiveGroup = useCallback(
    (groupId: number | null) => {
      activeGroupRef.current = groupId
      if (groupId === null) return
      queryClient.setQueryData<Record<number, number>>(chatKeys.unread(), (prev) => {
        if (!prev?.[groupId]) return prev
        const next = { ...prev }
        delete next[groupId]
        return next
      })
    },
    [queryClient],
  )

  const socketRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<number>(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Guards against a reconnect scheduled by an old socket resurrecting itself
  // after the user has logged out or the component has unmounted.
  const cancelledRef = useRef(false)
  // True from the start of a connection attempt until its socket exists.
  const connectingRef = useRef(false)
  // Pending "this connection has lasted long enough" timer, cancelled if the
  // socket closes before it fires.
  const stableTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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

          // Your own messages are not news, and neither are messages in the
          // conversation you already have open in front of you.
          const isMine =
            message.user_id !== null && message.user_id === userIdRef.current

          // Counting is an increment, so unlike every other handler here it is
          // not idempotent — the same frame arriving twice would inflate the
          // badge. Message ids only ever increase, so refusing to count one we
          // have already counted makes a duplicate delivery harmless.
          const alreadyCounted = message.id <= (countedThroughRef.current[message.group_id] ?? 0)

          if (!isMine && !alreadyCounted && activeGroupRef.current !== message.group_id) {
            countedThroughRef.current[message.group_id] = message.id
            queryClient.setQueryData<Record<number, number>>(
              chatKeys.unread(),
              (prev) => ({ ...prev, [message.group_id]: (prev?.[message.group_id] ?? 0) + 1 }),
            )
          }
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

  const clearStableTimer = useCallback(() => {
    if (stableTimerRef.current) {
      clearTimeout(stableTimerRef.current)
      stableTimerRef.current = null
    }
  }, [])

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
    // `socketRef` is only assigned after the ticket round trip, so it cannot on
    // its own stop two overlapping attempts from both reaching the constructor
    // and leaving a second, unreferenced socket open forever. React's dev
    // double-mount does exactly that: the first attempt is in flight when the
    // second starts, and each ends up delivering its own copy of every frame.
    if (socketRef.current || connectingRef.current) return

    connectingRef.current = true
    let ticket: string
    try {
      ticket = (await messageService.createTicket()).ticket
    } catch {
      // Could not mint a ticket (offline, server down). Back off and retry —
      // the app works without the socket, it just falls back to polling.
      scheduleRetry()
      return
    } finally {
      // Released here rather than after the constructor: no await separates the
      // two, so nothing can interleave, and every exit path is covered.
      connectingRef.current = false
    }
    if (cancelledRef.current) return

    const socket = new WebSocket(socketUrl(ticket))
    socketRef.current = socket

    socket.onopen = () => {
      setIsConnected(true)
      // Forgive the backoff only once this connection has proven it lasts.
      clearStableTimer()
      stableTimerRef.current = setTimeout(() => {
        stableTimerRef.current = null
        retryRef.current = 0
      }, STABLE_AFTER_MS)
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
      // Closed before proving stable, so the backoff counter stands.
      clearStableTimer()
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
  }, [applyEvent, scheduleRetry, clearStableTimer])

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
      clearStableTimer()
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
  }, [user, connect, clearStableTimer])

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
    () => ({ isConnected, presenceByGroup, onlineUserIds, unreadByGroup, setActiveGroup }),
    [isConnected, presenceByGroup, onlineUserIds, unreadByGroup, setActiveGroup],
  )

  return <ChatSocketContext.Provider value={value}>{children}</ChatSocketContext.Provider>
}
