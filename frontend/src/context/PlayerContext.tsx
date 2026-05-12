import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSpotifyPlayer, type PlayerStatus } from '../hooks/useSpotifyPlayer'
import { useAuth } from '../hooks/useAuth'
import { statsService } from '../services/statsService'

export interface PlayingAlbumMeta {
  spotifyAlbumId: string
  title: string
  artist: string
  coverUrl: string | null
  appAlbumId: number
  groupId?: number
  groupAlbumId?: number
}

interface PlayerContextValue {
  status: PlayerStatus
  currentTrackUri: string | null
  currentTrackName: string | null
  currentTrackNumber: number | null
  position: number
  duration: number
  playingSpotifyAlbumId: string | null
  hasSpotify: boolean
  minimized: boolean
  toggleMinimized: () => void
  togglePlay: () => void
  skipNext: () => void
  skipPrevious: () => void
  seekTo: (positionMs: number) => void
  playingAlbumMeta: PlayingAlbumMeta | null
  startAlbum: (spotifyAlbumId: string, meta: PlayingAlbumMeta, trackUri?: string) => Promise<void>
  clearPlayer: () => void
}

const PlayerContext = createContext<PlayerContextValue | null>(null)

const STORAGE_KEY = 'spinshare_player'

interface PersistedState {
  playingAlbumMeta: PlayingAlbumMeta
  lastTrackUri: string | null
  lastPosition: number
  minimized: boolean
}

function loadPersistedState(): PersistedState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as PersistedState
  } catch {
    return null
  }
}

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const { data: stats } = useQuery({
    queryKey: ['stats', 'me'],
    queryFn: () => statsService.getMyStats(),
    enabled: !!user,
  })
  const hasSpotify = stats?.has_spotify ?? false

  // Load persisted state once (lazy useState initializer)
  const [persistedState] = useState<PersistedState | null>(loadPersistedState)

  const [playingAlbumMeta, setPlayingAlbumMeta] = useState<PlayingAlbumMeta | null>(
    persistedState?.playingAlbumMeta ?? null
  )
  const [minimized, setMinimized] = useState(persistedState?.minimized ?? true)
  const toggleMinimized = () => setMinimized((m) => !m)

  const player = useSpotifyPlayer(hasSpotify)

  // Auto-resume: once the SDK is ready, restore the last playing track and position
  const autoResumedRef = useRef(false)
  useEffect(() => {
    if (autoResumedRef.current) return
    if (!persistedState?.playingAlbumMeta) return
    if (player.status !== 'ready') return
    autoResumedRef.current = true
    player.startAlbum(
      persistedState.playingAlbumMeta.spotifyAlbumId,
      persistedState.lastTrackUri ?? undefined,
      persistedState.lastPosition ?? undefined,
    )
  }, [player.status]) // eslint-disable-line react-hooks/exhaustive-deps

  // Persist player state to localStorage whenever track or minimized state changes.
  // Position is written separately on beforeunload to avoid a write every 250 ms.
  useEffect(() => {
    if (!playingAlbumMeta) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    try {
      const state: PersistedState = { playingAlbumMeta, lastTrackUri: player.currentTrackUri, lastPosition: 0, minimized }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {}
  }, [playingAlbumMeta, player.currentTrackUri, minimized])

  // Keep a ref to the latest position so beforeunload can read it without stale closure issues
  const positionRef = useRef(player.position)
  useEffect(() => { positionRef.current = player.position }, [player.position])

  useEffect(() => {
    const handleBeforeUnload = () => {
      try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) return
        const state = JSON.parse(raw) as PersistedState
        state.lastPosition = positionRef.current
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
      } catch {}
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  const startAlbum = async (spotifyAlbumId: string, meta: PlayingAlbumMeta, trackUri?: string) => {
    setPlayingAlbumMeta(meta)
    await player.startAlbum(spotifyAlbumId, trackUri)
  }

  const clearPlayer = () => setPlayingAlbumMeta(null)

  return (
    <PlayerContext.Provider value={{
      status: player.status,
      currentTrackUri: player.currentTrackUri,
      currentTrackName: player.currentTrackName,
      currentTrackNumber: player.currentTrackNumber,
      position: player.position,
      duration: player.duration,
      playingSpotifyAlbumId: player.playingSpotifyAlbumId,
      hasSpotify,
      minimized,
      toggleMinimized,
      togglePlay: player.togglePlay,
      skipNext: player.skipNext,
      skipPrevious: player.skipPrevious,
      seekTo: player.seekTo,
      playingAlbumMeta,
      startAlbum,
      clearPlayer,
    }}>
      {children}
    </PlayerContext.Provider>
  )
}

export function usePlayer(): PlayerContextValue {
  const ctx = useContext(PlayerContext)
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider')
  return ctx
}
