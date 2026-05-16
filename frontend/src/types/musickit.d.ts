declare namespace MusicKit {
  interface MediaItemAttributes {
    name: string
    trackNumber: number
    durationInMillis: number
    artistName: string
    albumName: string
  }

  interface MediaItem {
    id: string
    attributes: MediaItemAttributes
    container: { id: string } | null
  }

  interface Queue {
    items: MediaItem[]
    position: number
  }

  interface LibraryAPI {
    add(options: { albums?: string[]; songs?: string[] }): Promise<void>
  }

  interface MusicKitAPI {
    library: LibraryAPI
  }

  interface MusicKitInstance {
    isAuthorized: boolean
    musicUserToken: string | null
    playbackState: number
    currentPlaybackTime: number
    currentPlaybackDuration: number
    nowPlayingItem: MediaItem | null
    queue: Queue | null
    api: MusicKitAPI
    authorize(): Promise<string>
    unauthorize(): Promise<void>
    play(): Promise<void>
    pause(): Promise<void>
    skipToNextItem(): Promise<void>
    skipToPreviousItem(): Promise<void>
    seekToTime(time: number): Promise<void>
    changeToMediaAtIndex(index: number): Promise<void>
    setQueue(options: { album?: string; song?: string }): Promise<void>
    addEventListener(event: string, handler: (event: unknown) => void): void
    removeEventListener(event: string, handler: (event: unknown) => void): void
  }

  const PlaybackStates: {
    none: 0
    loading: 1
    playing: 2
    paused: 3
    stopped: 4
    ended: 5
    seeking: 6
    waiting: 9
    stalled: 10
    completed: 11
  }

  function configure(config: {
    developerToken: string
    app: { name: string; build: string }
  }): Promise<MusicKitInstance>

  function getInstance(): MusicKitInstance
}

interface Window {
  MusicKit: typeof MusicKit
}
