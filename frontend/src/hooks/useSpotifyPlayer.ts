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

export interface SpotifyTrack {
  name: string
  artists: string
  albumName: string
  coverUrl: string | null
  durationMs: number
  positionMs: number
}

export interface UseSpotifyPlayerResult {
  status: PlayerStatus
  currentTrack: SpotifyTrack | null
  deviceId: string | null
  togglePlay: () => void
  nextTrack: () => void
  prevTrack: () => void
  startAlbum: (spotifyAlbumId: string) => Promise<void>
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
  const [currentTrack, setCurrentTrack] = useState<SpotifyTrack | null>(null)
  const [deviceId, setDeviceId] = useState<string | null>(null)
  const playerRef = useRef<Spotify.Player | null>(null)
  const tokenRef = useRef<string | null>(null)

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
            setDeviceId(device_id)
            setStatus('ready')
          }
        })

        player.addListener('not_ready', () => {
          if (!cancelled) setStatus('loading')
        })

        player.addListener('player_state_changed', (state: Spotify.PlaybackState | null) => {
          if (cancelled || !state) return
          const track = state.track_window.current_track
          setCurrentTrack({
            name: track.name,
            artists: track.artists.map((a) => a.name).join(', '),
            albumName: track.album.name,
            coverUrl: track.album.images[0]?.url ?? null,
            durationMs: state.duration,
            positionMs: state.position,
          })
          setStatus(state.paused ? 'paused' : 'playing')
        })

        player.addListener('initialization_error', () => {
          if (!cancelled) setStatus('error')
        })

        player.addListener('authentication_error', () => {
          if (!cancelled) setStatus('reconnect_required')
        })

        // Fires when user doesn't have Spotify Premium
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
      playerRef.current?.disconnect()
      playerRef.current = null
    }
  }, [enabled])

  const togglePlay = () => playerRef.current?.togglePlay()
  const nextTrack = () => playerRef.current?.nextTrack()
  const prevTrack = () => playerRef.current?.previousTrack()

  const startAlbum = async (spotifyAlbumId: string) => {
    if (!deviceId || !tokenRef.current) return
    try {
      await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${tokenRef.current}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ context_uri: `spotify:album:${spotifyAlbumId}` }),
      })
    } catch {
      // Non-critical — player will still be connected, user can retry
    }
  }

  return { status, currentTrack, deviceId, togglePlay, nextTrack, prevTrack, startAlbum }
}
