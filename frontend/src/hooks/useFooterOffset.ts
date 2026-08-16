import { usePlayer } from '../context/PlayerContext'

/**
 * Height currently occupied by the player footer, or 0 when it is hidden.
 *
 * Shared by AppShell (which reserves the space) and anything floating above the
 * page that must sit clear of it — otherwise the two would drift apart the
 * first time the player's dimensions change.
 */
export function useFooterOffset(): number {
  const { status, playingAlbumMeta, minimized } = usePlayer()

  const showFooter =
    playingAlbumMeta !== null &&
    (status === 'ready' || status === 'playing' || status === 'paused')

  if (!showFooter) return 0
  return minimized ? 48 : 220
}
