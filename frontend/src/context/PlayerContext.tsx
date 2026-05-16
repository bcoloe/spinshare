import { createContext, useContext, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSpotifyPlayer, type PlayerStatus } from '../hooks/useSpotifyPlayer'
import { useAppleMusicPlayer } from '../hooks/useAppleMusicPlayer'
import { useAuth } from '../hooks/useAuth'
import { statsService } from '../services/statsService'
import { getSpotifyToken, getAppleMusicDeveloperToken } from '../services/streamingService'
import {
  fetchAlbumTracks,
  isAlbumSaved,
  saveAlbum,
  unsaveAlbum,
} from '../services/spotifyApiClient'

export interface PlayingAlbumMeta {
  spotifyAlbumId: string
  appleMusicAlbumId?: string | null
  title: string
  artist: string
  coverUrl: string | null
  appAlbumId: number
  groupId?: number
  groupAlbumId?: number
}

export type ActiveService = 'spotify' | 'apple_music'

export interface UnifiedTrack {
  id: string       // Spotify URI or Apple Music catalog song ID
  name: string
  trackNumber: number
  durationMs: number
  artist: string
}

interface PlayerContextValue {
  status: PlayerStatus
  currentTrackUri: string | null
  currentTrackName: string | null
  currentTrackNumber: number | null
  position: number
  duration: number
  playingSpotifyAlbumId: string | null
  playingAppleMusicAlbumId: string | null
  hasSpotify: boolean
  hasAppleMusic: boolean
  preferredService: ActiveService
  setPreferredService: (service: ActiveService) => void
  activeService: ActiveService | null
  minimized: boolean
  toggleMinimized: () => void
  togglePlay: () => void
  skipNext: () => void
  skipPrevious: () => void
  seekTo: (positionMs: number) => void
  playingAlbumMeta: PlayingAlbumMeta | null
  startAlbum: (spotifyAlbumId: string, meta: PlayingAlbumMeta, trackUri?: string) => Promise<void>
  playInAppleMusic: (meta: PlayingAlbumMeta) => Promise<void>
  connectAppleMusic: () => Promise<void>
  disconnectAppleMusic: () => Promise<void>
  clearPlayer: () => void
  // Unified track list
  tracks: UnifiedTrack[]
  tracksLoading: boolean
  skipToTrack: (index: number) => void
  // Unified library
  albumSaved: boolean
  albumSavePending: boolean
  toggleAlbumSave: () => Promise<void>
  canRemoveFromLibrary: boolean
  // Apple Music tokens (for playlist modal)
  appleMusicUserToken: string | null
  appleMusicDeveloperToken: string | null
  nowPlayingSongId: string | null
}

const PlayerContext = createContext<PlayerContextValue | null>(null)

const STORAGE_KEY = 'spinshare_player'
const PREF_KEY = 'spinshare_preferred_service'

function loadPreferredService(): ActiveService {
  try {
    const raw = localStorage.getItem(PREF_KEY)
    if (raw === 'apple_music' || raw === 'spotify') return raw
  } catch {}
  return 'spotify'
}

interface PersistedState {
  playingAlbumMeta: PlayingAlbumMeta
  lastTrackUri: string | null
  lastTrackName: string | null
  lastTrackNumber: number | null
  lastPosition: number
  lastDuration: number
  minimized: boolean
  activeService: ActiveService
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

  const [persistedState] = useState<PersistedState | null>(loadPersistedState)

  const [playingAlbumMeta, setPlayingAlbumMeta] = useState<PlayingAlbumMeta | null>(
    persistedState?.playingAlbumMeta ?? null
  )
  const [minimized, setMinimized] = useState(persistedState?.minimized ?? true)
  const [activeService, setActiveService] = useState<ActiveService | null>(
    persistedState?.activeService ?? null
  )
  const [preferredService, setPreferredServiceState] = useState<ActiveService>(loadPreferredService)
  const toggleMinimized = () => setMinimized((m) => !m)

  const setPreferredService = (service: ActiveService) => {
    setPreferredServiceState(service)
    try { localStorage.setItem(PREF_KEY, service) } catch {}
  }

  const player = useSpotifyPlayer(hasSpotify)
  const applePlayer = useAppleMusicPlayer()

  const hasAppleMusic = applePlayer.isAuthorized

  // Derive the unified status from whichever service is currently active
  const status = activeService === 'apple_music' ? applePlayer.status : player.status

  // Track name/number from whichever service is active
  const currentTrackName = activeService === 'apple_music'
    ? (applePlayer.playingAppleMusicAlbumId ? applePlayer.currentTrackName : (persistedState?.lastTrackName ?? null))
    : player.currentTrackName
  const currentTrackNumber = activeService === 'apple_music'
    ? applePlayer.currentTrackNumber
    : player.currentTrackNumber

  // ── Unified track list ─────────────────────────────────────────────────────

  const [tracks, setTracks] = useState<UnifiedTrack[]>([])
  const [tracksLoading, setTracksLoading] = useState(false)

  // Fetch Spotify tracks when Spotify album starts
  useEffect(() => {
    if (activeService !== 'spotify' || !playingAlbumMeta) {
      if (activeService !== 'apple_music') setTracks([])
      return
    }
    let cancelled = false
    setTracksLoading(true)
    getSpotifyToken()
      .then((token) => fetchAlbumTracks(token, playingAlbumMeta.spotifyAlbumId))
      .then((t) => {
        if (!cancelled) setTracks(t.map((track) => ({
          id: track.uri,
          name: track.name,
          trackNumber: track.trackNumber,
          durationMs: track.durationMs,
          artist: track.artists,
        })))
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setTracksLoading(false) })
    return () => { cancelled = true }
  }, [activeService, playingAlbumMeta?.spotifyAlbumId, hasSpotify])

  // Sync Apple Music queue tracks reactively
  useEffect(() => {
    if (activeService !== 'apple_music') return
    setTracks(applePlayer.queueTracks.map((t) => ({
      id: t.id,
      name: t.name,
      trackNumber: t.trackNumber,
      durationMs: t.durationMs,
      artist: t.artistName,
    })))
  }, [activeService, applePlayer.queueTracks])

  const skipToTrack = (index: number) => {
    if (activeService === 'apple_music') {
      applePlayer.skipToTrackAtIndex(index)
      return
    }
    const track = tracks[index]
    if (!track || !playingAlbumMeta) return
    player.startAlbum(playingAlbumMeta.spotifyAlbumId, track.id)
  }

  // ── Unified library save ───────────────────────────────────────────────────

  const [albumSaved, setAlbumSaved] = useState(false)
  const [albumSavePending, setAlbumSavePending] = useState(false)

  useEffect(() => {
    if (activeService !== 'spotify' || !playingAlbumMeta) {
      setAlbumSaved(false)
      return
    }
    let cancelled = false
    getSpotifyToken()
      .then((token) => isAlbumSaved(token, playingAlbumMeta.spotifyAlbumId))
      .then((saved) => { if (!cancelled) setAlbumSaved(saved) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [activeService, playingAlbumMeta?.spotifyAlbumId])

  const toggleAlbumSave = async () => {
    if (!playingAlbumMeta) return
    setAlbumSavePending(true)
    try {
      if (activeService === 'apple_music') {
        const albumId = playingAlbumMeta.appleMusicAlbumId
        if (albumId) await applePlayer.saveAlbumToLibrary(albumId)
        return
      }
      const token = await getSpotifyToken()
      if (albumSaved) {
        await unsaveAlbum(token, playingAlbumMeta.spotifyAlbumId)
        setAlbumSaved(false)
      } else {
        await saveAlbum(token, playingAlbumMeta.spotifyAlbumId)
        setAlbumSaved(true)
      }
    } finally {
      setAlbumSavePending(false)
    }
  }

  // Apple Music: can only add to library, not remove
  const canRemoveFromLibrary = activeService === 'spotify' && albumSaved

  // ── Apple Music tokens ─────────────────────────────────────────────────────

  const [appleMusicDeveloperToken, setAppleMusicDeveloperToken] = useState<string | null>(null)

  useEffect(() => {
    if (!hasAppleMusic) return
    getAppleMusicDeveloperToken()
      .then(setAppleMusicDeveloperToken)
      .catch(() => {})
  }, [hasAppleMusic])

  // ── Persist player state ───────────────────────────────────────────────────

  useEffect(() => {
    if (!playingAlbumMeta || !activeService) {
      localStorage.removeItem(STORAGE_KEY)
      return
    }
    try {
      const state: PersistedState = {
        playingAlbumMeta,
        lastTrackUri: activeService === 'spotify' ? player.currentTrackUri : null,
        lastTrackName: activeService === 'apple_music' ? applePlayer.currentTrackName : player.currentTrackName,
        lastTrackNumber: activeService === 'apple_music' ? applePlayer.currentTrackNumber : null,
        lastPosition: 0,
        lastDuration: activeService === 'apple_music' ? applePlayer.duration : player.duration,
        minimized,
        activeService,
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {}
  }, [playingAlbumMeta, player.currentTrackUri, applePlayer.currentTrackName, applePlayer.currentTrackNumber, minimized, activeService])

  const positionRef = useRef(player.position)
  useEffect(() => { positionRef.current = player.position }, [player.position])

  const appleMusicPositionRef = useRef(applePlayer.position)
  useEffect(() => { appleMusicPositionRef.current = applePlayer.position }, [applePlayer.position])

  const appleMusicDurationRef = useRef(applePlayer.duration)
  useEffect(() => { appleMusicDurationRef.current = applePlayer.duration }, [applePlayer.duration])

  useEffect(() => {
    const handleBeforeUnload = () => {
      try {
        const raw = localStorage.getItem(STORAGE_KEY)
        if (!raw) return
        const state = JSON.parse(raw) as PersistedState
        if (state.activeService === 'apple_music') {
          state.lastPosition = appleMusicPositionRef.current
          state.lastDuration = appleMusicDurationRef.current
        } else {
          state.lastPosition = positionRef.current
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
      } catch {}
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [])

  // ── Playback ───────────────────────────────────────────────────────────────

  const needsRestore = activeService === 'spotify' && !player.playingSpotifyAlbumId && !!playingAlbumMeta
  const needsRestoreAppleMusic = activeService === 'apple_music' && !applePlayer.playingAppleMusicAlbumId && !!playingAlbumMeta
  const currentTrackUri = needsRestore ? (persistedState?.lastTrackUri ?? null) : player.currentTrackUri
  const position = activeService === 'apple_music'
    ? (needsRestoreAppleMusic ? (persistedState?.lastPosition ?? 0) : applePlayer.position)
    : needsRestore ? (persistedState?.lastPosition ?? 0) : player.position
  const duration = activeService === 'apple_music'
    ? (needsRestoreAppleMusic ? (persistedState?.lastDuration ?? 0) : applePlayer.duration)
    : needsRestore ? (persistedState?.lastDuration ?? 0) : player.duration

  const startAlbum = async (spotifyAlbumId: string, meta: PlayingAlbumMeta, trackUri?: string) => {
    setPlayingAlbumMeta(meta)
    setActiveService('spotify')
    await player.startAlbum(spotifyAlbumId, trackUri)
  }

  const playInAppleMusic = async (meta: PlayingAlbumMeta) => {
    if (!meta.appleMusicAlbumId) return
    setPlayingAlbumMeta(meta)
    setActiveService('apple_music')
    await applePlayer.startAlbum(meta.appleMusicAlbumId)
  }

  const togglePlay = () => {
    if (activeService === 'apple_music') {
      if (!applePlayer.playingAppleMusicAlbumId && playingAlbumMeta?.appleMusicAlbumId) {
        const lastTrackIndex = (persistedState?.lastTrackNumber ?? 1) - 1
        applePlayer.startAlbum(
          playingAlbumMeta.appleMusicAlbumId,
          persistedState?.lastPosition ?? undefined,
          lastTrackIndex > 0 ? lastTrackIndex : undefined,
        )
        return
      }
      applePlayer.togglePlay()
      return
    }
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

  const skipNext = () => {
    if (activeService === 'apple_music') { applePlayer.skipNext(); return }
    player.skipNext()
  }

  const skipPrevious = () => {
    if (activeService === 'apple_music') { applePlayer.skipPrevious(); return }
    player.skipPrevious()
  }

  const seekTo = (positionMs: number) => {
    if (activeService === 'apple_music') { applePlayer.seekTo(positionMs); return }
    player.seekTo(positionMs)
  }

  const clearPlayer = () => {
    setPlayingAlbumMeta(null)
    setActiveService(null)
  }

  const connectAppleMusic = () => applePlayer.authorize()

  const disconnectAppleMusic = async () => {
    await applePlayer.unauthorize()
    if (activeService === 'apple_music') clearPlayer()
  }

  return (
    <PlayerContext.Provider value={{
      status,
      currentTrackUri,
      currentTrackName,
      currentTrackNumber,
      position,
      duration,
      playingSpotifyAlbumId: player.playingSpotifyAlbumId,
      playingAppleMusicAlbumId: applePlayer.playingAppleMusicAlbumId,
      hasSpotify,
      hasAppleMusic,
      preferredService,
      setPreferredService,
      activeService,
      minimized,
      toggleMinimized,
      togglePlay,
      skipNext,
      skipPrevious,
      seekTo,
      playingAlbumMeta,
      startAlbum,
      playInAppleMusic,
      connectAppleMusic,
      disconnectAppleMusic,
      clearPlayer,
      tracks,
      tracksLoading,
      skipToTrack,
      albumSaved,
      albumSavePending,
      toggleAlbumSave,
      canRemoveFromLibrary,
      appleMusicUserToken: applePlayer.musicUserToken,
      appleMusicDeveloperToken,
      nowPlayingSongId: activeService === 'apple_music' ? applePlayer.nowPlayingSongId : currentTrackUri,
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
