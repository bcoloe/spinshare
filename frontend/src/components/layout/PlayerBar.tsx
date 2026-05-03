import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ActionIcon,
  Divider,
  Group,
  Image,
  Menu,
  Slider,
  Stack,
  Text,
  Tooltip,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import { notifications } from '@mantine/notifications'
import {
  IconBrandSpotify,
  IconChevronDown,
  IconChevronUp,
  IconDots,
  IconExternalLink,
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
import { isAlbumSaved, saveAlbum, unsaveAlbum } from '../../services/spotifyApiClient'

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
    currentTrackNumber,
    position,
    duration,
    playingAlbumMeta,
    minimized,
    toggleMinimized,
    togglePlay,
    skipNext,
    skipPrevious,
    seekTo,
  } = usePlayer()

  const [seekValue, setSeekValue] = useState<number | null>(null)
  const [albumSaved, setAlbumSaved] = useState(false)
  const [savingAlbum, setSavingAlbum] = useState(false)
  const [pickerUris, setPickerUris] = useState<string[]>([])
  const [pickerTitle, setPickerTitle] = useState('Add to playlist')
  const [pickerOpened, { open: openPicker, close: closePicker }] = useDisclosure(false)

  const isPlaying = status === 'playing'
  const displayPosition = seekValue ?? position
  const progressPercent = duration > 0 ? (displayPosition / duration) * 100 : 0

  // Re-check saved state whenever the loaded album changes
  useEffect(() => {
    if (!playingAlbumMeta) return
    let cancelled = false
    getSpotifyToken()
      .then((token) => isAlbumSaved(token, playingAlbumMeta.spotifyAlbumId))
      .then((saved) => { if (!cancelled) setAlbumSaved(saved) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [playingAlbumMeta?.spotifyAlbumId])

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
    // We don't have the full tracklist here — open picker with a signal to the
    // album context URI so the user can add the whole album
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

  // ── Minimized layout ──────────────────────────────────────────────────────
  if (minimized) {
    return (
      <>
        <Group h="100%" px="md" gap="sm" wrap="nowrap" style={borderTop}>
          <Image
            src={playingAlbumMeta?.coverUrl ?? undefined}
            w={28}
            h={28}
            radius="xs"
            style={{ flexShrink: 0 }}
            fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='28' height='28'%3E%3Crect width='28' height='28' fill='%23373A40'/%3E%3C/svg%3E"
          />
          <Text size="sm" lineClamp={1} style={{ flex: 1, minWidth: 0 }}>
            {currentTrackName
              ? <><Text span fw={500}>{currentTrackName}</Text><Text span c="dimmed"> · {playingAlbumMeta?.title}</Text></>
              : <Text span c="dimmed">{playingAlbumMeta?.title ?? '—'}</Text>}
          </Text>
          <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
            <ActionIcon variant="filled" color="green" radius="xl" size="sm" onClick={togglePlay}>
              {isPlaying ? <IconPlayerPauseFilled size={12} /> : <IconPlayerPlayFilled size={12} />}
            </ActionIcon>
            <KebabMenu
              albumSaved={albumSaved}
              savingAlbum={savingAlbum}
              hasTrack={!!currentTrackUri}
              onToggleSave={handleToggleSaveAlbum}
              onAddAlbum={handleOpenAlbumPicker}
              onAddTrack={handleOpenTrackPicker}
            />
            <Tooltip label="Expand player" withArrow>
              <ActionIcon variant="subtle" size="sm" color="gray" onClick={toggleMinimized} aria-label="Expand player">
                <IconChevronUp size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Group>
        <PlaylistPickerModal opened={pickerOpened} onClose={closePicker} uris={pickerUris} title={pickerTitle} />
      </>
    )
  }

  // ── Full layout ───────────────────────────────────────────────────────────
  return (
    <>
      <Group h="100%" px="md" gap="md" wrap="nowrap" style={borderTop}>
        {/* Left: album identity */}
        <Group gap="sm" wrap="nowrap" style={{ flex: '0 0 auto', minWidth: 0, maxWidth: 220 }}>
          <Image
            src={playingAlbumMeta?.coverUrl ?? undefined}
            w={44}
            h={44}
            radius="sm"
            style={{ flexShrink: 0 }}
            fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='44' height='44'%3E%3Crect width='44' height='44' fill='%23373A40'/%3E%3C/svg%3E"
          />
          <Stack gap={0} style={{ minWidth: 0, flex: 1 }}>
            <Text size="sm" fw={500} lineClamp={1}>{playingAlbumMeta?.title ?? '—'}</Text>
            <Text size="xs" c="dimmed" lineClamp={1}>{playingAlbumMeta?.artist ?? ''}</Text>
          </Stack>
          {playingAlbumMeta?.appAlbumId && (
            <Tooltip label="Go to album" withArrow>
              <ActionIcon
                component={Link}
                to={`/albums/${playingAlbumMeta.appAlbumId}`}
                variant="subtle"
                size="sm"
                color="gray"
                style={{ flexShrink: 0 }}
              >
                <IconExternalLink size={14} />
              </ActionIcon>
            </Tooltip>
          )}
        </Group>

        {/* Center: track name → seek bar → controls */}
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }} align="center">
          <Text size="xs" c="dimmed" lineClamp={1} style={{ maxWidth: '100%' }}>
            {currentTrackName
              ? <>{currentTrackNumber != null && <Text span c="dimmed">{currentTrackNumber}. </Text>}<Text span fw={500} c="white">{currentTrackName}</Text></>
              : (isPlaying ? 'Playing' : status === 'paused' ? 'Paused' : 'Ready')}
          </Text>
          <Group gap="xs" w="100%" wrap="nowrap">
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
                seekTo((val / 100) * duration)
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
          <Group gap={4}>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipPrevious} disabled={!currentTrackUri}>
              <IconPlayerSkipBackFilled size={14} />
            </ActionIcon>
            <ActionIcon variant="filled" color="green" radius="xl" size="md" onClick={togglePlay}>
              {isPlaying ? <IconPlayerPauseFilled size={14} /> : <IconPlayerPlayFilled size={14} />}
            </ActionIcon>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={skipNext} disabled={!currentTrackUri}>
              <IconPlayerSkipForwardFilled size={14} />
            </ActionIcon>
          </Group>
        </Stack>

        {/* Right: brand + kebab + minimize */}
        <Group gap="xs" wrap="nowrap" justify="flex-end" style={{ flex: '0 0 auto', minWidth: 0 }}>
          <IconBrandSpotify size={14} color="#1DB954" style={{ flexShrink: 0 }} />
          <KebabMenu
            albumSaved={albumSaved}
            savingAlbum={savingAlbum}
            hasTrack={!!currentTrackUri}
            onToggleSave={handleToggleSaveAlbum}
            onAddAlbum={handleOpenAlbumPicker}
            onAddTrack={handleOpenTrackPicker}
          />
          <Tooltip label="Minimize player" withArrow>
            <ActionIcon variant="subtle" size="sm" color="gray" onClick={toggleMinimized} aria-label="Minimize player">
              <IconChevronDown size={14} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

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
  onToggleSave: () => void
  onAddAlbum: () => void
  onAddTrack: () => void
}

function KebabMenu({ albumSaved, savingAlbum, hasTrack, groupId, onToggleSave, onAddAlbum, onAddTrack }: KebabMenuProps) {
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
              to={`/groups/${groupId}/spin`}
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
