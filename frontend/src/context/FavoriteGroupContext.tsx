import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useAuth } from '../hooks/useAuth'

const FAVORITE_KEY = (username: string) => `spinshare_favorite_group_${username}`

interface FavoriteGroupContextValue {
  favoriteId: number | null
  toggleFavorite: (groupId: number) => void
  clearIfStale: (groupIds: number[]) => void
}

const FavoriteGroupContext = createContext<FavoriteGroupContextValue>({
  favoriteId: null,
  toggleFavorite: () => {},
  clearIfStale: () => {},
})

export function FavoriteGroupProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [favoriteId, setFavoriteIdState] = useState<number | null>(null)

  useEffect(() => {
    if (!user?.username) return
    const stored = localStorage.getItem(FAVORITE_KEY(user.username))
    setFavoriteIdState(stored ? parseInt(stored, 10) : null)
  }, [user?.username])

  const setFavoriteId = useCallback((id: number | null) => {
    setFavoriteIdState(id)
    if (!user?.username) return
    if (id === null) {
      localStorage.removeItem(FAVORITE_KEY(user.username))
    } else {
      localStorage.setItem(FAVORITE_KEY(user.username), String(id))
    }
  }, [user?.username])

  const toggleFavorite = useCallback((groupId: number) => {
    setFavoriteId(favoriteId === groupId ? null : groupId)
  }, [favoriteId, setFavoriteId])

  const clearIfStale = useCallback((groupIds: number[]) => {
    if (favoriteId !== null && !groupIds.includes(favoriteId)) {
      setFavoriteId(null)
    }
  }, [favoriteId, setFavoriteId])

  return (
    <FavoriteGroupContext.Provider value={{ favoriteId, toggleFavorite, clearIfStale }}>
      {children}
    </FavoriteGroupContext.Provider>
  )
}

export const useFavoriteGroup = () => useContext(FavoriteGroupContext)
