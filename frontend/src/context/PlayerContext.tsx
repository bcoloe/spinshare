import { createContext, useContext, useState } from 'react'
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

export function PlayerProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  const { data: stats } = useQuery({
    queryKey: ['stats', 'me'],
    queryFn: () => statsService.getMyStats(),
    enabled: !!user,
  })
  const hasSpotify = stats?.has_spotify ?? false

  const [playingAlbumMeta, setPlayingAlbumMeta] = useState<PlayingAlbumMeta | null>(null)
  const [minimized, setMinimized] = useState(false)
  const toggleMinimized = () => setMinimized((m) => !m)

  const player = useSpotifyPlayer(hasSpotify)

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
