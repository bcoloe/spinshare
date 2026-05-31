import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from '../hooks/useAuth'
import { useUnreadNotifications } from '../hooks/useNotifications'

// ==================== TYPES ====================

type UnseenKey = string // "{groupId}:{albumId}"

interface UnseenReviewsContextValue {
  isUnseen: (groupId: number, albumId: number) => boolean
  markSeen: (groupId: number, albumId: number) => void
}

// ==================== HELPERS ====================

const STORAGE_KEY = (username: string) => `spinshare_unseen_reviews_${username}`

function toKey(groupId: number, albumId: number): UnseenKey {
  return `${groupId}:${albumId}`
}

// ==================== CONTEXT ====================

const UnseenReviewsContext = createContext<UnseenReviewsContextValue>({
  isUnseen: () => false,
  markSeen: () => {},
})

export function UnseenReviewsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [unseen, setUnseen] = useState<Set<UnseenKey>>(new Set())
  const { data: unreadNotifications = [] } = useUnreadNotifications()

  // Hydrate from localStorage whenever the logged-in user changes.
  useEffect(() => {
    if (!user?.username) return
    const stored = localStorage.getItem(STORAGE_KEY(user.username))
    setUnseen(stored ? new Set(JSON.parse(stored) as UnseenKey[]) : new Set())
  }, [user?.username])

  // Sync a set to localStorage (stable reference via useCallback).
  const persist = useCallback(
    (set: Set<UnseenKey>) => {
      if (!user?.username) return
      localStorage.setItem(STORAGE_KEY(user.username), JSON.stringify([...set]))
    },
    [user?.username],
  )

  // Eagerly capture member_reviewed_album notifications as they arrive from
  // the polling query — before markAllRead fires when the bell is opened.
  useEffect(() => {
    const newKeys = unreadNotifications
      .filter((n) => n.type === 'member_reviewed_album' && n.group_id !== null && n.album_id !== null)
      .map((n) => toKey(n.group_id!, n.album_id!))

    if (newKeys.length === 0) return

    setUnseen((prev) => {
      if (newKeys.every((k) => prev.has(k))) return prev // nothing new
      const next = new Set(prev)
      for (const k of newKeys) next.add(k)
      persist(next)
      return next
    })
  }, [unreadNotifications, persist])

  const markSeen = useCallback(
    (groupId: number, albumId: number) => {
      const key = toKey(groupId, albumId)
      setUnseen((prev) => {
        if (!prev.has(key)) return prev
        const next = new Set(prev)
        next.delete(key)
        persist(next)
        return next
      })
    },
    [persist],
  )

  const isUnseen = useCallback(
    (groupId: number, albumId: number) => unseen.has(toKey(groupId, albumId)),
    [unseen],
  )

  return (
    <UnseenReviewsContext.Provider value={{ isUnseen, markSeen }}>
      {children}
    </UnseenReviewsContext.Provider>
  )
}

export const useUnseenReviews = () => useContext(UnseenReviewsContext)
