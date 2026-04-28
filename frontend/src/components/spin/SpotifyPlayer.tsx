import { useEffect, useRef, useState } from 'react'
import {
  ActionIcon,
  Alert,
  Anchor,
  Box,
  Collapse,
  Group,
  ScrollArea,
  Skeleton,
  Slider,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconAlertCircle,
  IconBrandSpotify,
  IconChevronDown,
  IconChevronUp,
  IconExternalLink,
  IconHeart,
  IconHeartFilled,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
  IconPlaylistAdd,
} from '@tabler/icons-react'
import { useSpotifyPlayer } from '../../hooks/useSpotifyPlayer'
import { getSpotifyToken } from '../../services/streamingService'
import {
  isAlbumSaved,
  saveAlbum,
  unsaveAlbum,
} from '../../services/spotifyApiClient'
import PlaylistPickerModal from './PlaylistPickerModal'

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
  onPlayingAlbumChange?: (spotifyAlbumId: string | null) => void
}

export default function SpotifyPlayer({ spotifyAlbumId, hasSpotify, onPlayingAlbumChange }: Props) {
  const { status, currentTrackUri, position, duration, playingSpotifyAlbumId, togglePlay, skipNext, skipPrevious, seekTo, startAlbum } =
    useSpotifyPlayer(hasSpotify, spotifyAlbumId)

  useEffect(() => {
    onPlayingAlbumChange?.(playingSpotifyAlbumId)
  }, [playingSpotifyAlbumId, onPlayingAlbumChange])

  const [tracks, setTracks] = useState<AlbumTrack[]>([])
  const [tracksLoading, setTracksLoading] = useState(false)
  const [albumSaved, setAlbumSaved] = useState(false)
  const [savingAlbum, setSavingAlbum] = useState(false)
  const [seekValue, setSeekValue] = useState<number | null>(null)
  const [tracklistOpen, setTracklistOpen] = useState(true)

  const [pickerUris, setPickerUris] = useState<string[]>([])
  const [pickerTitle, setPickerTitle] = useState('Add to playlist')
  const [pickerOpened, { open: openPicker, close: closePicker }] = useDisclosure(false)

  const activeTrackRef = useRef<HTMLDivElement | null>(null)

  // Reset per-album state when the album changes (component may persist across tab switches)
  useEffect(() => {
    setTracks([])
    setAlbumSaved(false)
    setSeekValue(null)
  }, [spotifyAlbumId])

  // Fetch tracklist once the player is in an active state
  useEffect(() => {
    if (!hasSpotify || (status !== 'ready' && status !== 'playing' && status !== 'paused')) return
    if (tracks.length > 0) return

    let cancelled = false
    setTracksLoading(true)

    async function fetchTracks() {
      try {
        const token = await getSpotifyToken()
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

  // Check saved state once tracks load
  useEffect(() => {
    if (!hasSpotify || tracks.length === 0) return
    getSpotifyToken()
      .then((token) => isAlbumSaved(token, spotifyAlbumId))
      .then(setAlbumSaved)
      .catch(() => {})
  }, [hasSpotify, tracks.length, spotifyAlbumId])

  // Scroll the active track into view when it changes
  useEffect(() => {
    activeTrackRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [currentTrackUri])

  const handleToggleSaveAlbum = async () => {
    setSavingAlbum(true)
    try {
      const token = await getSpotifyToken()
      if (albumSaved) {
        await unsaveAlbum(token, spotifyAlbumId)
        setAlbumSaved(false)
        notifications.show({ message: 'Removed from Your Library' })
      } else {
        await saveAlbum(token, spotifyAlbumId)
        setAlbumSaved(true)
        notifications.show({ color: 'green', message: 'Saved to Your Library' })
      }
    } catch (err) {
      notifications.show({ color: 'red', message: err instanceof Error ? err.message : 'Could not update library' })
    } finally {
      setSavingAlbum(false)
    }
  }

  const handleOpenPicker = (target: 'album' | string) => {
    setPickerUris(target === 'album' ? tracks.map((t) => t.uri) : [target])
    setPickerTitle(target === 'album' ? 'Add album to playlist' : 'Add track to playlist')
    openPicker()
  }

  const displayPosition = seekValue ?? position
  const progressPercent = duration > 0 ? (displayPosition / duration) * 100 : 0

  const openLink = `https://open.spotify.com/album/${spotifyAlbumId}`

  if (!hasSpotify) return <IframeFallback spotifyAlbumId={spotifyAlbumId} />

  if (status === 'loading' || status === 'idle') return <Skeleton h={300} radius="md" />

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

  if (status === 'not_connected') return <IframeFallback spotifyAlbumId={spotifyAlbumId} />

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
  const isActive = status === 'playing' || status === 'paused'

  return (
    <>
      <Stack gap="xs">
        <Box
          style={(theme) => ({
            background: theme.colors.dark[7],
            borderRadius: theme.radius.md,
            border: `1px solid ${theme.colors.dark[4]}`,
            overflow: 'hidden',
          })}
        >
          {/* Controls + album actions header */}
          <Group
            px="sm"
            py="xs"
            gap="sm"
            justify="space-between"
            style={(theme) => ({ borderBottom: isActive ? 'none' : `1px solid ${theme.colors.dark[5]}` })}
          >
            <Group gap={4} style={{ minWidth: 0, flex: 1 }}>
              <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipPrevious} disabled={!isActive}>
                <IconPlayerSkipBackFilled size={14} />
              </ActionIcon>
              <ActionIcon
                variant="filled"
                color="green"
                radius="xl"
                size="md"
                onClick={() => status === 'ready' ? startAlbum(spotifyAlbumId) : togglePlay()}
              >
                {isPlaying ? <IconPlayerPauseFilled size={14} /> : <IconPlayerPlayFilled size={14} />}
              </ActionIcon>
              <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipNext} disabled={!isActive}>
                <IconPlayerSkipForwardFilled size={14} />
              </ActionIcon>
              <Text size="sm" c={currentTrackUri ? 'white' : 'dimmed'} fw={currentTrackUri ? 500 : 400} lineClamp={1} style={{ flex: 1, marginLeft: 4 }}>
                {isPlaying && currentTrackUri
                  ? tracks.find((t) => t.uri === currentTrackUri)?.name ?? 'Playing…'
                  : status === 'paused' && currentTrackUri
                  ? `Paused · ${tracks.find((t) => t.uri === currentTrackUri)?.name ?? ''}`
                  : 'Ready to play'}
              </Text>
            </Group>

            {/* Album-level actions */}
            <Group gap={4} wrap="nowrap">
              <Tooltip label={albumSaved ? 'Remove from library' : 'Save album'} withArrow>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  color={albumSaved ? 'green' : 'gray'}
                  loading={savingAlbum}
                  onClick={handleToggleSaveAlbum}
                >
                  {albumSaved ? <IconHeartFilled size={14} /> : <IconHeart size={14} />}
                </ActionIcon>
              </Tooltip>
              <Tooltip label="Add album to playlist" withArrow>
                <ActionIcon variant="subtle" size="sm" onClick={() => handleOpenPicker('album')} disabled={tracks.length === 0}>
                  <IconPlaylistAdd size={14} />
                </ActionIcon>
              </Tooltip>
              <Tooltip label={tracklistOpen ? 'Hide tracklist' : 'Show tracklist'} withArrow>
                <ActionIcon variant="subtle" size="sm" color="gray" onClick={() => setTracklistOpen((o) => !o)}>
                  {tracklistOpen ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>

          {/* Progress bar */}
          {isActive && (
            <Box px="sm" pb={6} style={(theme) => ({ borderBottom: `1px solid ${theme.colors.dark[5]}` })}>
              <Group gap="xs" align="center" wrap="nowrap">
                <Text size="xs" c="dimmed" w={32} ta="right" style={{ flexShrink: 0 }}>
                  {formatDuration(displayPosition)}
                </Text>
                <Slider
                  style={{ flex: 1 }}
                  size="xs"
                  value={progressPercent}
                  min={0}
                  max={100}
                  step={0.01}
                  label={null}
                  thumbSize={10}
                  onChange={(val) => setSeekValue((val / 100) * duration)}
                  onChangeEnd={(val) => {
                    const ms = (val / 100) * duration
                    seekTo(ms)
                    setSeekValue(null)
                  }}
                  styles={(theme) => ({
                    track: { background: theme.colors.dark[4] },
                    bar: { background: '#1DB954' },
                    thumb: { borderColor: '#1DB954', background: '#1DB954' },
                  })}
                />
                <Text size="xs" c="dimmed" w={32} style={{ flexShrink: 0 }}>
                  {formatDuration(duration)}
                </Text>
              </Group>
            </Box>
          )}

          {/* Tracklist */}
          <Collapse in={tracklistOpen}>
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
                      <Group
                        key={track.uri}
                        ref={isActive ? activeTrackRef : null}
                        px="sm"
                        py={7}
                        gap="xs"
                        wrap="nowrap"
                        className="track-row"
                        style={(theme) => ({
                          cursor: 'pointer',
                          background: isActive ? theme.colors.dark[5] : 'transparent',
                          borderLeft: isActive ? '2px solid #1DB954' : '2px solid transparent',
                        })}
                        onClick={() => startAlbum(spotifyAlbumId, track.uri)}
                      >
                        <Text size="xs" c="dimmed" w={20} ta="right" style={{ flexShrink: 0 }}>
                          {isActive ? <IconBrandSpotify size={12} color="#1DB954" /> : track.trackNumber}
                        </Text>
                        <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
                          <Text size="sm" c={isActive ? 'green.4' : undefined} fw={isActive ? 500 : 400} lineClamp={1}>
                            {track.name}
                          </Text>
                          <Text size="xs" c="dimmed" lineClamp={1}>{track.artists}</Text>
                        </Stack>
                        <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
                          {formatDuration(track.durationMs)}
                        </Text>
                        <Tooltip label="Add to playlist" withArrow>
                          <ActionIcon
                            variant="subtle"
                            size="xs"
                            style={{ flexShrink: 0 }}
                            onClick={(e) => { e.stopPropagation(); handleOpenPicker(track.uri) }}
                          >
                            <IconPlaylistAdd size={12} />
                          </ActionIcon>
                        </Tooltip>
                      </Group>
                    )
                  })}
            </ScrollArea>
          </Collapse>
        </Box>

        <Anchor href={openLink} target="_blank" rel="noopener noreferrer" size="sm" c="dimmed">
          <Group gap={4}>
            <IconExternalLink size={14} />
            Open in Spotify
          </Group>
        </Anchor>
      </Stack>

      <PlaylistPickerModal
        opened={pickerOpened}
        onClose={closePicker}
        uris={pickerUris}
        title={pickerTitle}
      />
    </>
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
