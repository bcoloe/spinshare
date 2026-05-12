import { useEffect, useRef, useState } from 'react'
import { getSpotifyToken } from '../services/streamingService'
import { ApiError } from '../services/apiClient'

export type PlayerStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'playing'
  | 'paused'
  | 'premium_required'
  | 'not_connected'
  | 'reconnect_required'
  | 'error'

export interface UseSpotifyPlayerResult {
  status: PlayerStatus
  currentTrackUri: string | null
  currentTrackName: string | null
  currentTrackNumber: number | null
  position: number
  duration: number
  deviceId: string | null
  /** Spotify album ID currently playing in the SDK player, null if nothing is playing. Independent of which album tab is active. */
  playingSpotifyAlbumId: string | null
  togglePlay: () => void
  skipNext: () => void
  skipPrevious: () => void
  seekTo: (positionMs: number) => void
  startAlbum: (spotifyAlbumId: string, trackUri?: string, positionMs?: number) => Promise<void>
}

// Load the Spotify Web Playback SDK script once globally.
let sdkScriptLoaded = false
function loadSpotifySdk(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve()
  if (window.Spotify) return Promise.resolve()
  if (sdkScriptLoaded) {
    return new Promise((resolve) => {
      const existing = window.onSpotifyWebPlaybackSDKReady
      window.onSpotifyWebPlaybackSDKReady = () => {
        existing?.()
        resolve()
      }
    })
  }
  return new Promise((resolve) => {
    window.onSpotifyWebPlaybackSDKReady = resolve
    const script = document.createElement('script')
    script.src = 'https://sdk.scdn.co/spotify-player.js'
    script.async = true
    document.body.appendChild(script)
    sdkScriptLoaded = true
  })
}

export function useSpotifyPlayer(enabled: boolean): UseSpotifyPlayerResult {
  const [status, setStatus] = useState<PlayerStatus>('idle')
  const [currentTrackUri, setCurrentTrackUri] = useState<string | null>(null)
  const [currentTrackName, setCurrentTrackName] = useState<string | null>(null)
  const [currentTrackNumber, setCurrentTrackNumber] = useState<number | null>(null)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const [deviceId, setDeviceId] = useState<string | null>(null)
  const [playingSpotifyAlbumId, setPlayingSpotifyAlbumId] = useState<string | null>(null)

  const playerRef = useRef<Spotify.Player | null>(null)
  const tokenRef = useRef<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const basePositionRef = useRef(0)
  const baseTimestampRef = useRef(0)
  const isPlayingRef = useRef(false)
  const deviceIdRef = useRef<string | null>(null)

  function startProgressInterval() {
    if (intervalRef.current) return
    intervalRef.current = setInterval(() => {
      if (!isPlayingRef.current) return
      setPosition(basePositionRef.current + (Date.now() - baseTimestampRef.current))
    }, 250)
  }

  function stopProgressInterval() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  useEffect(() => {
    if (!enabled) return

    let cancelled = false
    setStatus('loading')

    async function init() {
      try {
        await loadSpotifySdk()
        if (cancelled) return

        const player = new window.Spotify.Player({
          name: 'SpinShare',
          getOAuthToken: async (cb) => {
            try {
              const token = await getSpotifyToken()
              tokenRef.current = token
              cb(token)
            } catch (err) {
              if (err instanceof ApiError && err.status === 401) {
                setStatus('reconnect_required')
              } else if (err instanceof ApiError && err.status === 404) {
                setStatus('not_connected')
              } else {
                setStatus('error')
              }
            }
          },
          volume: 0.7,
        })

        player.addListener('ready', ({ device_id }: { device_id: string }) => {
          if (!cancelled) {
            deviceIdRef.current = device_id
            setDeviceId(device_id)
            setStatus('ready')
            startProgressInterval()
          }
        })

        player.addListener('not_ready', () => {
          if (!cancelled) setStatus('loading')
        })

        player.addListener('player_state_changed', (state: Spotify.PlaybackState | null) => {
          if (cancelled) return
          if (!state) {
            setCurrentTrackUri(null)
            setCurrentTrackName(null)
            setCurrentTrackNumber(null)
            setPlayingSpotifyAlbumId(null)
            setStatus((prev) => (prev === 'playing' || prev === 'paused') ? 'ready' : prev)
            return
          }
          const track = state.track_window.current_track
          setPlayingSpotifyAlbumId(track.album.uri.split(':')[2])

          basePositionRef.current = state.position
          baseTimestampRef.current = Date.now()
          isPlayingRef.current = !state.paused

          setCurrentTrackUri(track.uri)
          setCurrentTrackName(track.name)
          setCurrentTrackNumber(track.track_number)
          setDuration(state.duration)
          setPosition(state.position)
          setStatus(state.paused ? 'paused' : 'playing')
        })

        player.addListener('initialization_error', () => {
          if (!cancelled) setStatus('error')
        })

        player.addListener('authentication_error', () => {
          if (!cancelled) setStatus('reconnect_required')
        })

        player.addListener('account_error', () => {
          if (!cancelled) setStatus('premium_required')
        })

        await player.connect()
        playerRef.current = player
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 404) {
            setStatus('not_connected')
          } else if (err instanceof ApiError && err.status === 401) {
            setStatus('reconnect_required')
          } else {
            setStatus('error')
          }
        }
      }
    }

    init()

    return () => {
      cancelled = true
      stopProgressInterval()
      playerRef.current?.disconnect()
      playerRef.current = null
    }
  }, [enabled])

  const togglePlay = () => playerRef.current?.togglePlay()
  const skipNext = () => playerRef.current?.nextTrack()
  const skipPrevious = () => playerRef.current?.previousTrack()

  const seekTo = (positionMs: number) => {
    basePositionRef.current = positionMs
    baseTimestampRef.current = Date.now()
    setPosition(positionMs)
    playerRef.current?.seek(positionMs)
  }

  const startAlbum = async (albumId: string, trackUri?: string, positionMs?: number) => {
    if (!deviceIdRef.current || !tokenRef.current) return
    const body: Record<string, unknown> = { context_uri: `spotify:album:${albumId}` }
    if (trackUri) body.offset = { uri: trackUri }
    if (positionMs && positionMs > 0) body.position_ms = Math.floor(positionMs)
    try {
      await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${deviceIdRef.current}`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${tokenRef.current}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      })
    } catch {
      // Non-critical — player will still be connected, user can retry
    }
  }

  return { status, currentTrackUri, currentTrackName, currentTrackNumber, position, duration, deviceId, playingSpotifyAlbumId, togglePlay, skipNext, skipPrevious, seekTo, startAlbum }
}
