import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ActionIcon,
  Anchor,
  Divider,
  Group,
  Image,
  Menu,
  ScrollArea,
  Slider,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconChevronDown,
  IconChevronUp,
  IconDots,
  IconHeart,
  IconHeartFilled,
  IconMessageCircle,
  IconPlayerPauseFilled,
  IconPlayerPlayFilled,
  IconPlayerSkipBackFilled,
  IconPlayerSkipForwardFilled,
  IconPlaylistAdd,
} from '@tabler/icons-react'
import { usePlayer } from '../../context/PlayerContext'
import PlaylistPickerModal from '../spin/PlaylistPickerModal'
import { getSpotifyToken } from '../../services/streamingService'
import {
  fetchAlbumTracks,
  isAlbumSaved,
  saveAlbum,
  unsaveAlbum,
  type AlbumTrack,
} from '../../services/spotifyApiClient'

function formatDuration(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  return `${min}:${sec.toString().padStart(2, '0')}`
}

export default function PlayerBar() {
  const {
    status,
    currentTrackUri,
    currentTrackName,
    position,
    duration,
    playingAlbumMeta,
    minimized,
    toggleMinimized,
    togglePlay,
    skipNext,
    skipPrevious,
    seekTo,
    startAlbum,
  } = usePlayer()

  const [seekValue, setSeekValue] = useState<number | null>(null)
  const [albumSaved, setAlbumSaved] = useState(false)
  const [savingAlbum, setSavingAlbum] = useState(false)
  const [pickerUris, setPickerUris] = useState<string[]>([])
  const [pickerTitle, setPickerTitle] = useState('Add to playlist')
  const [pickerOpened, { open: openPicker, close: closePicker }] = useDisclosure(false)

  const [tracks, setTracks] = useState<AlbumTrack[]>([])
  const [tracksLoading, setTracksLoading] = useState(false)
  const activeTrackRef = useRef<HTMLDivElement | null>(null)

  const isPlaying = status === 'playing'
  const displayPosition = seekValue ?? position
  const progressPercent = duration > 0 ? (displayPosition / duration) * 100 : 0

  useEffect(() => {
    if (!playingAlbumMeta) return
    let cancelled = false
    getSpotifyToken()
      .then((token) => isAlbumSaved(token, playingAlbumMeta.spotifyAlbumId))
      .then((saved) => { if (!cancelled) setAlbumSaved(saved) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [playingAlbumMeta?.spotifyAlbumId])

  useEffect(() => {
    if (!playingAlbumMeta?.spotifyAlbumId) {
      setTracks([])
      return
    }
    let cancelled = false
    setTracksLoading(true)
    getSpotifyToken()
      .then((token) => fetchAlbumTracks(token, playingAlbumMeta.spotifyAlbumId))
      .then((t) => { if (!cancelled) setTracks(t) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setTracksLoading(false) })
    return () => { cancelled = true }
  }, [playingAlbumMeta?.spotifyAlbumId])

  useEffect(() => {
    activeTrackRef.current?.scrollIntoView({ block: 'nearest' })
  }, [currentTrackUri])

  const handleJumpToTrack = (trackUri: string) => {
    if (!playingAlbumMeta) return
    startAlbum(playingAlbumMeta.spotifyAlbumId, playingAlbumMeta, trackUri)
  }

  const handleToggleSaveAlbum = async () => {
    if (!playingAlbumMeta) return
    setSavingAlbum(true)
    try {
      const token = await getSpotifyToken()
      if (albumSaved) {
        await unsaveAlbum(token, playingAlbumMeta.spotifyAlbumId)
        setAlbumSaved(false)
        notifications.show({ message: 'Removed from Your Library' })
      } else {
        await saveAlbum(token, playingAlbumMeta.spotifyAlbumId)
        setAlbumSaved(true)
        notifications.show({ color: 'green', message: 'Saved to Your Library' })
      }
    } catch (err) {
      notifications.show({ color: 'red', message: err instanceof Error ? err.message : 'Could not update library' })
    } finally {
      setSavingAlbum(false)
    }
  }

  const handleOpenAlbumPicker = () => {
    setPickerUris(playingAlbumMeta ? [`spotify:album:${playingAlbumMeta.spotifyAlbumId}`] : [])
    setPickerTitle('Add album to playlist')
    openPicker()
  }

  const handleOpenTrackPicker = () => {
    if (!currentTrackUri) return
    setPickerUris([currentTrackUri])
    setPickerTitle('Add track to playlist')
    openPicker()
  }

  const borderTop = { borderTop: '1px solid var(--mantine-color-dark-4)' }
  const separator = '1px solid var(--mantine-color-dark-4)'

  return (
    <>
      <Stack h="100%" gap={0} style={borderTop}>

        {/* Tracklist — revealed when expanded */}
        {!minimized && (
          <ScrollArea style={{ flex: 1, minHeight: 0 }} scrollbarSize={4}>
            {tracksLoading && (
              <Text size="xs" c="dimmed" px="md" py="xs">Loading tracks…</Text>
            )}
            {tracks.map((track) => (
              <div key={track.uri} ref={track.uri === currentTrackUri ? activeTrackRef : undefined}>
                <Group
                  px="md"
                  py={6}
                  gap="xs"
                  wrap="nowrap"
                  style={{
                    cursor: 'pointer',
                    backgroundColor: track.uri === currentTrackUri ? 'var(--mantine-color-dark-6)' : 'transparent',
                  }}
                  onClick={() => handleJumpToTrack(track.uri)}
                >
                  <Text size="xs" w={24} ta="right" style={{ flexShrink: 0 }} c={track.uri === currentTrackUri ? 'green' : 'dimmed'}>
                    {track.trackNumber}
                  </Text>
                  <Stack gap={0} style={{ flex: 1, minWidth: 0 }}>
                    <Text size="xs" fw={track.uri === currentTrackUri ? 600 : 400} c={track.uri === currentTrackUri ? 'green' : 'white'} lineClamp={1}>
                      {track.name}
                    </Text>
                    <Text size="xs" c="dimmed" lineClamp={1}>{track.artists}</Text>
                  </Stack>
                  <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>{formatDuration(track.durationMs)}</Text>
                </Group>
              </div>
            ))}
          </ScrollArea>
        )}

        {/* Bar — always visible */}
        <Group
          h={48}
          px="md"
          gap="sm"
          wrap="nowrap"
          style={{ flexShrink: 0, ...(!minimized && { borderTop: separator }) }}
        >
          <Image
            src={playingAlbumMeta?.coverUrl ?? undefined}
            w={28}
            h={28}
            radius="xs"
            style={{ flexShrink: 0 }}
            fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='28'%3E%3Crect width='28' height='28' fill='%23373A40'/%3E%3C/svg%3E"
          />

          <Stack gap={1} style={{ flex: 1, minWidth: 0 }}>
            <Text size="xs" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {currentTrackName && <Text span fw={500} size="xs">{currentTrackName}</Text>}
              {currentTrackName && playingAlbumMeta?.artist && <Text span c="dimmed" size="xs"> · </Text>}
              {playingAlbumMeta?.artist && <Text span c="dimmed" size="xs">{playingAlbumMeta.artist}</Text>}
              {playingAlbumMeta?.artist && <Text span c="dimmed" size="xs"> · </Text>}
              {playingAlbumMeta?.appAlbumId ? (
                <Anchor component={Link} to={`/albums/${playingAlbumMeta.appAlbumId}`} c="dimmed" size="xs" underline="hover">
                  {playingAlbumMeta.title ?? '—'}
                </Anchor>
              ) : (
                <Text span c="dimmed" size="xs">{playingAlbumMeta?.title ?? '—'}</Text>
              )}
            </Text>
            <Group gap={4} wrap="nowrap">
              <Text size="xs" c="dimmed" ta="right" style={{ flexShrink: 0, width: 28 }}>
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
                thumbSize={8}
                onChange={(val) => setSeekValue((val / 100) * duration)}
                onChangeEnd={(val) => {
                  seekTo((val / 100) * duration)
                  setSeekValue(null)
                }}
                styles={(theme) => ({
                  track: { background: theme.colors.dark[4] },
                  bar: { background: '#1DB954' },
                  thumb: { borderColor: '#1DB954', background: '#1DB954' },
                })}
              />
              <Text size="xs" c="dimmed" style={{ flexShrink: 0, width: 28 }}>
                {formatDuration(duration)}
              </Text>
            </Group>
          </Stack>

          <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipPrevious} disabled={!currentTrackUri}>
              <IconPlayerSkipBackFilled size={12} />
            </ActionIcon>
            <ActionIcon variant="filled" color="green" radius="xl" size="sm" onClick={togglePlay}>
              {isPlaying ? <IconPlayerPauseFilled size={12} /> : <IconPlayerPlayFilled size={12} />}
            </ActionIcon>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipNext} disabled={!currentTrackUri}>
              <IconPlayerSkipForwardFilled size={12} />
            </ActionIcon>
            <KebabMenu
              albumSaved={albumSaved}
              savingAlbum={savingAlbum}
              hasTrack={!!currentTrackUri}
              groupId={playingAlbumMeta?.groupId}
              groupAlbumId={playingAlbumMeta?.groupAlbumId}
              onToggleSave={handleToggleSaveAlbum}
              onAddAlbum={handleOpenAlbumPicker}
              onAddTrack={handleOpenTrackPicker}
            />
            <Tooltip label={minimized ? 'Show tracklist' : 'Hide tracklist'} withArrow>
              <ActionIcon variant="subtle" size="sm" color="gray" onClick={toggleMinimized} aria-label={minimized ? 'Show tracklist' : 'Hide tracklist'}>
                {minimized ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>

      </Stack>
      <PlaylistPickerModal opened={pickerOpened} onClose={closePicker} uris={pickerUris} title={pickerTitle} />
    </>
  )
}

// ── Kebab menu ────────────────────────────────────────────────────────────────

interface KebabMenuProps {
  albumSaved: boolean
  savingAlbum: boolean
  hasTrack: boolean
  groupId?: number
  groupAlbumId?: number
  onToggleSave: () => void
  onAddAlbum: () => void
  onAddTrack: () => void
}

function KebabMenu({ albumSaved, savingAlbum, hasTrack, groupId, groupAlbumId, onToggleSave, onAddAlbum, onAddTrack }: KebabMenuProps) {
  return (
    <Menu shadow="md" width={210} position="top-end" withinPortal>
      <Menu.Target>
        <Tooltip label="More options" withArrow>
          <ActionIcon variant="subtle" size="sm" color="gray" aria-label="More options">
            <IconDots size={14} />
          </ActionIcon>
        </Tooltip>
      </Menu.Target>
      <Menu.Dropdown>
        {groupId && (
          <>
            <Menu.Item
              component={Link}
              to={groupAlbumId
                ? `/groups/${groupId}?tab=spin&album=${groupAlbumId}`
                : `/groups/${groupId}?tab=spin`}
              leftSection={<IconMessageCircle size={14} />}
            >
              Go to review
            </Menu.Item>
            <Divider />
          </>
        )}
        <Menu.Item
          leftSection={albumSaved ? <IconHeartFilled size={14} color="var(--mantine-color-green-5)" /> : <IconHeart size={14} />}
          onClick={onToggleSave}
          disabled={savingAlbum}
        >
          {albumSaved ? 'Remove from library' : 'Save album'}
        </Menu.Item>
        <Menu.Item leftSection={<IconPlaylistAdd size={14} />} onClick={onAddAlbum}>
          Add album to playlist
        </Menu.Item>
        <Divider />
        <Menu.Item leftSection={<IconPlaylistAdd size={14} />} onClick={onAddTrack} disabled={!hasTrack}>
          Add track to playlist
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  )
}
