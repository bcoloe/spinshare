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
  lastTrackName: string | null
  lastPosition: number
  lastDuration: number
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

  // Persist player state to localStorage whenever track or minimized state changes.
  // Position is written separately on beforeunload to avoid a write every 250 ms.
  useEffect(() => {
    if (!playingAlbumMeta) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    try {
      const state: PersistedState = {
        playingAlbumMeta,
        lastTrackUri: player.currentTrackUri,
        lastTrackName: player.currentTrackName,
        lastPosition: 0,
        lastDuration: player.duration,
        minimized,
      }
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

  // When the SDK has no track (e.g. after a refresh), show persisted values
  // so the player bar displays the correct track and progress before first play.
  const needsRestore = !player.playingSpotifyAlbumId && !!playingAlbumMeta
  const currentTrackUri = needsRestore ? (persistedState?.lastTrackUri ?? null) : player.currentTrackUri
  const currentTrackName = needsRestore ? (persistedState?.lastTrackName ?? null) : player.currentTrackName
  const position = needsRestore ? (persistedState?.lastPosition ?? 0) : player.position
  const duration = needsRestore ? (persistedState?.lastDuration ?? 0) : player.duration

  const startAlbum = async (spotifyAlbumId: string, meta: PlayingAlbumMeta, trackUri?: string) => {
    setPlayingAlbumMeta(meta)
    await player.startAlbum(spotifyAlbumId, trackUri)
  }

  // If the SDK has no track yet (e.g. after a page refresh) but we have
  // persisted state, load the saved track and position on the first play
  // rather than toggling nothing.
  const togglePlay = () => {
    if (!player.playingSpotifyAlbumId && playingAlbumMeta) {
      player.startAlbum(
        playingAlbumMeta.spotifyAlbumId,
        persistedState?.lastTrackUri ?? undefined,
        persistedState?.lastPosition ?? undefined,
      )
      return
    }
    player.togglePlay()
  }

  const clearPlayer = () => setPlayingAlbumMeta(null)

  return (
    <PlayerContext.Provider value={{
      status: player.status,
      currentTrackUri,
      currentTrackName,
      currentTrackNumber: player.currentTrackNumber,
      position,
      duration,
      playingSpotifyAlbumId: player.playingSpotifyAlbumId,
      hasSpotify,
      minimized,
      toggleMinimized,
      togglePlay,
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
