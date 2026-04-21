import { useEffect, useRef, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Anchor,
  Box,
  Group,
  ScrollArea,
  Skeleton,
  Stack,
  Text,
} from '@mantine/core'
import {
  IconAlertCircle,
  IconBrandSpotify,
  IconExternalLink,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
} from '@tabler/icons-react'
import { useSpotifyPlayer } from '../../hooks/useSpotifyPlayer'
import { getSpotifyToken } from '../../services/streamingService'

interface AlbumTrack {
  uri: string
  name: string
  trackNumber: number
  durationMs: number
  artists: string
}

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

interface Props {
  spotifyAlbumId: string
  hasSpotify: boolean
}

export default function SpotifyPlayer({ spotifyAlbumId, hasSpotify }: Props) {
  const { status, currentTrackUri, deviceId, togglePlay, startAlbum } =
    useSpotifyPlayer(hasSpotify, spotifyAlbumId)

  const [tracks, setTracks] = useState<AlbumTrack[]>([])
  const [tracksLoading, setTracksLoading] = useState(false)
  const activeTrackRef = useRef<HTMLDivElement | null>(null)

  // Fetch tracklist once when the player is ready and we have a token
  useEffect(() => {
    if (!hasSpotify || (status !== 'ready' && status !== 'playing' && status !== 'paused')) return
    if (tracks.length > 0) return

    let cancelled = false
    setTracksLoading(true)

    async function fetchTracks() {
      try {
        const token = await getSpotifyToken()
        // Fetch up to 50 tracks; covers virtually all albums
        const resp = await fetch(
          `https://api.spotify.com/v1/albums/${spotifyAlbumId}/tracks?limit=50`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        if (!resp.ok || cancelled) return
        const data = await resp.json()
        setTracks(
          data.items.map((t: { uri: string; name: string; track_number: number; duration_ms: number; artists: Array<{ name: string }> }) => ({
            uri: t.uri,
            name: t.name,
            trackNumber: t.track_number,
            durationMs: t.duration_ms,
            artists: t.artists.map((a) => a.name).join(', '),
          }))
        )
      } finally {
        if (!cancelled) setTracksLoading(false)
      }
    }

    fetchTracks()
    return () => { cancelled = true }
  }, [hasSpotify, status, spotifyAlbumId, tracks.length])

  // Scroll the active track into view when it changes
  useEffect(() => {
    activeTrackRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [currentTrackUri])

  // Auto-start the album once the device is ready
  useEffect(() => {
    if (status === 'ready' && deviceId) {
      startAlbum(spotifyAlbumId)
    }
  }, [status, deviceId, spotifyAlbumId])

  const openLink = `https://open.spotify.com/album/${spotifyAlbumId}`

  if (!hasSpotify) {
    return <IframeFallback spotifyAlbumId={spotifyAlbumId} />
  }

  if (status === 'loading' || status === 'idle') {
    return <Skeleton h={300} radius="md" />
  }

  if (status === 'premium_required') {
    return (
      <Stack gap="xs">
        <Alert icon={<IconBrandSpotify size={16} />} color="green" title="Spotify Premium required">
          Full playback is only available with Spotify Premium.
        </Alert>
        <IframeFallback spotifyAlbumId={spotifyAlbumId} />
      </Stack>
    )
  }

  if (status === 'reconnect_required') {
    return (
      <Alert icon={<IconAlertCircle size={16} />} color="orange" title="Spotify disconnected">
        Your Spotify session has expired.{' '}
        <Anchor href="/profile" size="sm">Reconnect in your profile</Anchor> to re-enable playback.
      </Alert>
    )
  }

  if (status === 'not_connected') {
    return <IframeFallback spotifyAlbumId={spotifyAlbumId} />
  }

  if (status === 'error') {
    return (
      <Stack gap="xs">
        <Alert icon={<IconAlertCircle size={16} />} color="red" title="Playback unavailable">
          Could not initialize the Spotify player.
        </Alert>
        <IframeFallback spotifyAlbumId={spotifyAlbumId} />
      </Stack>
    )
  }

  const isPlaying = status === 'playing'

  return (
    <Stack gap="xs">
      <Box
        style={(theme) => ({
          background: theme.colors.dark[7],
          borderRadius: theme.radius.md,
          border: `1px solid ${theme.colors.dark[4]}`,
          overflow: 'hidden',
        })}
      >
        {/* Playback controls header */}
        <Group
          px="sm"
          py="xs"
          gap="sm"
          style={(theme) => ({ borderBottom: `1px solid ${theme.colors.dark[5]}` })}
        >
          <ActionIcon
            variant="filled"
            color="green"
            radius="xl"
            size="md"
            onClick={togglePlay}
            disabled={status === 'ready'}
          >
            {isPlaying ? <IconPlayerPauseFilled size={14} /> : <IconPlayerPlayFilled size={14} />}
          </ActionIcon>
          <Text size="sm" c={currentTrackUri ? 'white' : 'dimmed'} fw={currentTrackUri ? 500 : 400}>
            {isPlaying && currentTrackUri
              ? tracks.find((t) => t.uri === currentTrackUri)?.name ?? 'Playing…'
              : status === 'paused' && currentTrackUri
              ? `Paused · ${tracks.find((t) => t.uri === currentTrackUri)?.name ?? ''}`
              : 'Ready to play'}
          </Text>
        </Group>

        {/* Tracklist */}
        <ScrollArea h={280} type="hover">
          {tracksLoading
            ? Array.from({ length: 6 }).map((_, i) => (
                <Box key={i} px="sm" py={6}>
                  <Skeleton h={14} radius="sm" />
                </Box>
              ))
            : tracks.map((track) => {
                const isActive = track.uri === currentTrackUri
                return (
                  <Box
                    key={track.uri}
                    ref={isActive ? activeTrackRef : null}
                    px="sm"
                    py={7}
                    onClick={() => startAlbum(spotifyAlbumId, track.uri)}
                    style={(theme) => ({
                      cursor: 'pointer',
                      background: isActive ? theme.colors.dark[5] : 'transparent',
                      borderLeft: isActive ? `2px solid #1DB954` : '2px solid transparent',
                      '&:hover': { background: theme.colors.dark[6] },
                    })}
                  >
                    <Group gap="xs" wrap="nowrap">
                      <Text
                        size="xs"
                        c="dimmed"
                        w={20}
                        ta="right"
                        style={{ flexShrink: 0 }}
                      >
                        {isActive ? (
                          <IconBrandSpotify size={12} color="#1DB954" />
                        ) : (
                          track.trackNumber
                        )}
                      </Text>
                      <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
                        <Text
                          size="sm"
                          c={isActive ? 'green.4' : undefined}
                          fw={isActive ? 500 : 400}
                          lineClamp={1}
                        >
                          {track.name}
                        </Text>
                        <Text size="xs" c="dimmed" lineClamp={1}>{track.artists}</Text>
                      </Stack>
                      <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                        {formatDuration(track.durationMs)}
                      </Text>
                    </Group>
                  </Box>
                )
              })}
        </ScrollArea>
      </Box>

      <Anchor href={openLink} target="_blank" rel="noopener noreferrer" size="sm" c="dimmed">
        <Group gap={4}>
          <IconExternalLink size={14} />
          Open in Spotify
        </Group>
      </Anchor>
    </Stack>
  )
}

function IframeFallback({ spotifyAlbumId }: { spotifyAlbumId: string }) {
  return (
    <Stack gap="xs">
      <iframe
        src={`https://open.spotify.com/embed/album/${spotifyAlbumId}?utm_source=generator&theme=0`}
        width="100%"
        height="352"
        frameBorder={0}
        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        loading="lazy"
        style={{ borderRadius: 12 }}
      />
      <Anchor
        href={`https://open.spotify.com/album/${spotifyAlbumId}`}
        target="_blank"
        rel="noopener noreferrer"
        size="sm"
        c="dimmed"
      >
        <Group gap={4}>
          <IconExternalLink size={14} />
          Open in Spotify
        </Group>
      </Anchor>
    </Stack>
  )
}
