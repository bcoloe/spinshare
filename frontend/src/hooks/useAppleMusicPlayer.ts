import { useEffect, useRef, useState } from 'react'
import { getAppleMusicDeveloperToken } from '../services/streamingService'
import type { PlayerStatus } from './useSpotifyPlayer'

export interface AppleMusicTrack {
  id: string
  name: string
  trackNumber: number
  durationMs: number
  artistName: string
}

export interface UseAppleMusicPlayerResult {
  status: PlayerStatus
  isAuthorized: boolean
  musicUserToken: string | null
  currentTrackName: string | null
  currentTrackNumber: number | null
  nowPlayingSongId: string | null
  position: number
  duration: number
  playingAppleMusicAlbumId: string | null
  queueTracks: AppleMusicTrack[]
  authorize: () => Promise<void>
  unauthorize: () => Promise<void>
  togglePlay: () => void
  skipNext: () => void
  skipPrevious: () => void
  seekTo: (positionMs: number) => void
  startAlbum: (appleMusicAlbumId: string, startPositionMs?: number, startTrackIndex?: number) => Promise<void>
  skipToTrackAtIndex: (index: number) => Promise<void>
  saveAlbumToLibrary: (albumId: string) => Promise<void>
}

let mkScriptLoaded = false

function loadMusicKitSdk(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve()
  if (window.MusicKit) return Promise.resolve()
  if (mkScriptLoaded) {
    return new Promise((resolve) => {
      const check = setInterval(() => {
        if (window.MusicKit) { clearInterval(check); resolve() }
      }, 100)
    })
  }
  return new Promise((resolve, reject) => {
    mkScriptLoaded = true
    const script = document.createElement('script')
    script.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js'
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Failed to load MusicKit JS'))
    document.body.appendChild(script)
  })
}

export function useAppleMusicPlayer(): UseAppleMusicPlayerResult {
  const [status, setStatus] = useState<PlayerStatus>('idle')
  const [isAuthorized, setIsAuthorized] = useState(false)
  const [musicUserToken, setMusicUserToken] = useState<string | null>(null)
  const [currentTrackName, setCurrentTrackName] = useState<string | null>(null)
  const [currentTrackNumber, setCurrentTrackNumber] = useState<number | null>(null)
  const [nowPlayingSongId, setNowPlayingSongId] = useState<string | null>(null)
  const [position, setPosition] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playingAppleMusicAlbumId, setPlayingAppleMusicAlbumId] = useState<string | null>(null)
  const [queueTracks, setQueueTracks] = useState<AppleMusicTrack[]>([])

  const musicRef = useRef<MusicKit.MusicKitInstance | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const currentAlbumIdRef = useRef<string | null>(null)

  function startProgressInterval() {
    if (intervalRef.current) return
    intervalRef.current = setInterval(() => {
      const music = musicRef.current
      if (!music) return
      setPosition(music.currentPlaybackTime * 1000)
      setDuration(music.currentPlaybackDuration * 1000)
    }, 250)
  }

  function stopProgressInterval() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  useEffect(() => {
    let cancelled = false

    const handleStateChange = () => {
      const music = musicRef.current
      if (!music || cancelled) return
      const state = music.playbackState
      if (state === 2) {
        setStatus('playing')
        startProgressInterval()
      } else if (state === 3) {
        setStatus('paused')
        stopProgressInterval()
      } else if (state === 0 || state === 4 || state === 5 || state === 11) {
        setStatus('ready')
        stopProgressInterval()
        setPosition(0)
      }
    }

    const handleTrackChange = () => {
      const music = musicRef.current
      if (!music || cancelled) return
      const item = music.nowPlayingItem
      if (!item) {
        setCurrentTrackName(null)
        setCurrentTrackNumber(null)
        return
      }
      setCurrentTrackName(item.attributes.name)
      setCurrentTrackNumber(item.attributes.trackNumber)
      setNowPlayingSongId(item.id)
      if (item.container?.id) {
        currentAlbumIdRef.current = item.container.id
        setPlayingAppleMusicAlbumId(item.container.id)
      }
    }

    const handleQueueChange = () => {
      const music = musicRef.current
      if (!music || cancelled) return
      const items = music.queue?.items ?? []
      setQueueTracks(
        items.map((item) => ({
          id: item.id,
          name: item.attributes.name,
          trackNumber: item.attributes.trackNumber,
          durationMs: item.attributes.durationInMillis,
          artistName: item.attributes.artistName,
        }))
      )
    }

    async function init() {
      try {
        setStatus('loading')
        await loadMusicKitSdk()
        if (cancelled) return

        const developerToken = await getAppleMusicDeveloperToken()
        if (cancelled) return

        await window.MusicKit.configure({
          developerToken,
          app: { name: 'SpinShare', build: '1.0.0' },
        })

        const music = window.MusicKit.getInstance()
        musicRef.current = music
        setIsAuthorized(music.isAuthorized)
        setMusicUserToken(music.musicUserToken)
        setStatus('ready')

        music.addEventListener('playbackStateDidChange', handleStateChange)
        music.addEventListener('nowPlayingItemDidChange', handleTrackChange)
        music.addEventListener('queueItemsDidChange', handleQueueChange)
      } catch {
        if (!cancelled) setStatus('error')
      }
    }

    init()

    return () => {
      cancelled = true
      stopProgressInterval()
      const music = musicRef.current
      if (music) {
        music.removeEventListener('playbackStateDidChange', handleStateChange)
        music.removeEventListener('nowPlayingItemDidChange', handleTrackChange)
        music.removeEventListener('queueItemsDidChange', handleQueueChange)
      }
    }
  }, [])

  const authorize = async () => {
    const music = musicRef.current
    if (!music) return
    await music.authorize()
    setIsAuthorized(music.isAuthorized)
    setMusicUserToken(music.musicUserToken)
  }

  const unauthorize = async () => {
    const music = musicRef.current
    if (!music) return
    await music.unauthorize()
    setIsAuthorized(false)
    setMusicUserToken(null)
  }

  const togglePlay = () => {
    const music = musicRef.current
    if (!music) return
    if (music.playbackState === 2) {
      music.pause()
    } else {
      music.play()
    }
  }

  const skipNext = () => musicRef.current?.skipToNextItem()
  const skipPrevious = () => musicRef.current?.skipToPreviousItem()

  const seekTo = (positionMs: number) => {
    setPosition(positionMs)
    musicRef.current?.seekToTime(positionMs / 1000)
  }

  const startAlbum = async (appleMusicAlbumId: string, startPositionMs?: number, startTrackIndex?: number) => {
    const music = musicRef.current
    if (!music) return
    if (!music.isAuthorized) {
      await music.authorize()
      setIsAuthorized(music.isAuthorized)
      if (!music.isAuthorized) return
    }
    currentAlbumIdRef.current = appleMusicAlbumId
    setPlayingAppleMusicAlbumId(appleMusicAlbumId)
    await music.setQueue({ album: appleMusicAlbumId })
    await music.play()
    if (startTrackIndex && startTrackIndex > 0) {
      try { await music.changeToMediaAtIndex(startTrackIndex) } catch {}
    }
    if (startPositionMs && startPositionMs > 0) {
      await music.seekToTime(startPositionMs / 1000)
    }
  }

  const skipToTrackAtIndex = async (index: number) => {
    const music = musicRef.current
    if (!music) return
    try {
      await music.changeToMediaAtIndex(index)
    } catch {
      // changeToMediaAtIndex may not be available in all versions; ignore
    }
  }

  const saveAlbumToLibrary = async (albumId: string) => {
    const music = musicRef.current
    if (!music?.isAuthorized) return
    await music.api.library.add({ albums: [albumId] })
  }

  return {
    status,
    isAuthorized,
    musicUserToken,
    currentTrackName,
    currentTrackNumber,
    nowPlayingSongId,
    position,
    duration,
    playingAppleMusicAlbumId,
    queueTracks,
    authorize,
    unauthorize,
    togglePlay,
    skipNext,
    skipPrevious,
    seekTo,
    startAlbum,
    skipToTrackAtIndex,
    saveAlbumToLibrary,
  }
}
