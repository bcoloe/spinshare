// Type declarations for the Spotify Web Playback SDK (loaded via CDN script tag).
// https://developer.spotify.com/documentation/web-playback-sdk/reference/

declare namespace Spotify {
  interface Player {
    connect(): Promise<boolean>
    disconnect(): void
    togglePlay(): Promise<void>
    nextTrack(): Promise<void>
    previousTrack(): Promise<void>
    getCurrentState(): Promise<PlaybackState | null>
    addListener(event: 'ready', cb: (data: { device_id: string }) => void): void
    addListener(event: 'not_ready', cb: (data: { device_id: string }) => void): void
    addListener(event: 'player_state_changed', cb: (state: PlaybackState | null) => void): void
    addListener(event: 'initialization_error', cb: (data: { message: string }) => void): void
    addListener(event: 'authentication_error', cb: (data: { message: string }) => void): void
    addListener(event: 'account_error', cb: (data: { message: string }) => void): void
  }

  interface PlayerInit {
    name: string
    getOAuthToken: (cb: (token: string) => void) => void
    volume?: number
  }

  interface PlaybackState {
    paused: boolean
    position: number
    duration: number
    track_window: {
      current_track: Track
    }
  }

  interface Track {
    name: string
    artists: Array<{ name: string }>
    album: {
      name: string
      images: Array<{ url: string }>
    }
  }

  const Player: new (init: PlayerInit) => Player
}

interface Window {
  Spotify: typeof Spotify
  onSpotifyWebPlaybackSDKReady: () => void
}
